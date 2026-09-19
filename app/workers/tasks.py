import logging
import statistics
import traceback
import uuid
from pathlib import Path

from app.database import SessionLocal
from app.models.document import Document, DocumentStatus, DocumentRole, Page
from app.models.question import Question, AnswerKeyEntry, QuestionStatus
from app.models.review import ReviewItem, ReviewSeverity
from app.services import answer_key as ak
from app.services import extraction as ext
from app.services import ocr
from app.services.storage import page_image_dir
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

CONFIDENCE_SUCCESS_THRESHOLD = 0.75
CONFIDENCE_PARTIAL_THRESHOLD = 0.45


def _classify_question_status(confidence: float) -> QuestionStatus:
    if confidence >= CONFIDENCE_SUCCESS_THRESHOLD:
        return QuestionStatus.SUCCESS
    if confidence >= CONFIDENCE_PARTIAL_THRESHOLD:
        return QuestionStatus.PARTIAL
    return QuestionStatus.REVIEW


@celery_app.task(name="process_document", bind=True, max_retries=1)
def process_document(self, document_id: str):
    db = SessionLocal()
    try:
        document = db.get(Document, uuid.UUID(document_id))
        if document is None:
            logger.error("Document %s not found", document_id)
            return

        document.status = DocumentStatus.PROCESSING
        db.commit()

        image_dir = page_image_dir(document.owner_id, document.id)
        page_results = ocr.extract_pages(document.stored_path, document.file_type, image_dir)

        if not page_results:
            raise ValueError("No pages could be extracted from the document")

        ocr_confidences = [p.ocr_confidence for p in page_results if p.ocr_confidence is not None]
        avg_ocr_confidence = statistics.mean(ocr_confidences) if ocr_confidences else None
        is_scanned = any(p.extraction_method == "ocr" for p in page_results)

        for pr in page_results:
            db.add(
                Page(
                    document_id=document.id,
                    page_number=pr.page_number,
                    raw_text=pr.text,
                    extraction_method=pr.extraction_method,
                    ocr_confidence=pr.ocr_confidence,
                    image_path=pr.image_path,
                    rotation_applied=pr.rotation_applied,
                )
            )
            if pr.ocr_confidence is not None and pr.ocr_confidence < 0.5:
                db.add(
                    ReviewItem(
                        document_id=document.id,
                        type="low_ocr_confidence",
                        severity=ReviewSeverity.WARNING,
                        message=f"Page {pr.page_number} OCR confidence is low ({pr.ocr_confidence:.2f}); text may be inaccurate.",
                    )
                )
            if pr.rotation_applied:
                db.add(
                    ReviewItem(
                        document_id=document.id,
                        type="rotation_corrected",
                        severity=ReviewSeverity.INFO,
                        message=f"Page {pr.page_number} was auto-rotated by {pr.rotation_applied} degrees.",
                    )
                )

        document.page_count = len(page_results)
        document.is_scanned = is_scanned

        pages_for_parsing = [(p.page_number, p.text) for p in page_results]
        answer_key_pages = ak.find_answer_key_section(pages_for_parsing)
        answer_key_coverage = len(answer_key_pages) / len(pages_for_parsing) if pages_for_parsing else 0

        # Heuristic role detection: if the whole document is essentially an answer
        # key, classify it as ANSWER_KEY; otherwise treat as (or default to) a
        # question paper and separately mine any trailing answer-key section.
        if answer_key_coverage >= 0.6:
            document.role = DocumentRole.ANSWER_KEY
        elif document.role == DocumentRole.UNKNOWN:
            document.role = DocumentRole.QUESTION_PAPER

        if document.role == DocumentRole.ANSWER_KEY:
            rows = ak.parse_answer_key(pages_for_parsing)
            if not rows:
                db.add(
                    ReviewItem(
                        document_id=document.id,
                        type="answer_key_unparseable",
                        severity=ReviewSeverity.CRITICAL,
                        message="Document was classified as an answer key but no answer entries could be parsed.",
                    )
                )
            for row in rows:
                db.add(
                    AnswerKeyEntry(
                        document_id=document.id,
                        group_id=document.group_id,
                        question_number=row.question_number,
                        answer_text=row.answer_text,
                        raw_line=row.raw_line,
                        source_page=row.source_page,
                        confidence=row.confidence,
                    )
                )
        else:
            # Question paper: extract questions from the non-answer-key pages.
            answer_key_page_numbers = {p for p, _ in answer_key_pages} if answer_key_coverage < 0.6 else set()
            question_pages = [(p, t) for p, t in pages_for_parsing if p not in answer_key_page_numbers]
            extracted = ext.extract_questions(question_pages, avg_ocr_confidence)

            if not extracted:
                db.add(
                    ReviewItem(
                        document_id=document.id,
                        type="no_questions_extracted",
                        severity=ReviewSeverity.CRITICAL,
                        message="No questions could be identified in this document.",
                    )
                )

            for eq in extracted:
                status_ = _classify_question_status(eq.confidence)
                question = Question(
                    document_id=document.id,
                    group_id=document.group_id,
                    question_number=eq.question_number,
                    question_text=eq.question_text,
                    options=eq.options,
                    question_type=eq.question_type,
                    source_pages=eq.source_pages,
                    spans_multiple_pages=eq.spans_multiple_pages,
                    confidence=round(eq.confidence, 3),
                    status=status_,
                )
                db.add(question)
                db.flush()  # get question.id for review-item linkage

                for warning in eq.warnings:
                    db.add(
                        ReviewItem(
                            document_id=document.id,
                            question_id=question.id,
                            type=warning,
                            severity=ReviewSeverity.WARNING if status_ != QuestionStatus.REVIEW else ReviewSeverity.CRITICAL,
                            message=f"Question {eq.question_number or '(unknown)'}: {warning.replace('_', ' ')}.",
                        )
                    )

            # Inline answer key found within the question paper itself.
            if answer_key_page_numbers:
                inline_rows = ak.parse_answer_key(answer_key_pages)
                for row in inline_rows:
                    db.add(
                        AnswerKeyEntry(
                            document_id=document.id,
                            group_id=document.group_id,
                            question_number=row.question_number,
                            answer_text=row.answer_text,
                            raw_line=row.raw_line,
                            source_page=row.source_page,
                            confidence=row.confidence,
                        )
                    )

        document.status = DocumentStatus.COMPLETED
        document.error_message = None
        db.commit()

        # Attempt answer-key <-> question matching across the whole group (or, if
        # ungrouped, just within this single document) now that this doc is done.
        match_answers_for_scope(db, document)

    except Exception as exc:  # noqa: BLE001
        db.rollback()
        document = db.get(Document, uuid.UUID(document_id))
        if document:
            document.status = DocumentStatus.FAILED
            document.error_message = f"{exc}"
            db.add(
                ReviewItem(
                    document_id=document.id,
                    type="processing_failed",
                    severity=ReviewSeverity.CRITICAL,
                    message=f"Processing failed: {exc}",
                )
            )
            db.commit()
        logger.error("Failed processing document %s: %s\n%s", document_id, exc, traceback.format_exc())
    finally:
        db.close()


def match_answers_for_scope(db, document: Document) -> None:
    """Matches AnswerKeyEntry rows to Question rows by question_number, scoped to
    the document's group when it belongs to one, else to the document itself."""
    if document.group_id:
        questions = db.query(Question).filter(Question.group_id == document.group_id).all()
        entries = db.query(AnswerKeyEntry).filter(AnswerKeyEntry.group_id == document.group_id).all()
    else:
        questions = db.query(Question).filter(Question.document_id == document.id).all()
        entries = db.query(AnswerKeyEntry).filter(AnswerKeyEntry.document_id == document.id).all()

    entries_by_number: dict[str, AnswerKeyEntry] = {}
    for e in entries:
        entries_by_number.setdefault(e.question_number, e)

    for q in questions:
        if not q.question_number:
            continue
        entry = entries_by_number.get(q.question_number)
        if entry is None:
            continue

        answer_text = entry.answer_text
        # If the question has lettered options, resolve "A" -> the option's full text too.
        matched_option = next((o for o in (q.options or []) if o.get("label", "").upper() == answer_text.upper()), None)

        q.answer = answer_text if not matched_option else f"{answer_text}: {matched_option['text']}"
        q.answer_confidence = round(min(entry.confidence, q.confidence + 0.1, 1.0), 3)
        q.answer_source = f"answer_key_doc:{entry.document_id}"
        entry.matched_question_id = q.id

    # Flag questions that have a number but never got matched to any answer key entry.
    unmatched_questions = [q for q in questions if q.question_number and q.answer is None]
    for q in unmatched_questions:
        existing = (
            db.query(ReviewItem)
            .filter(ReviewItem.question_id == q.id, ReviewItem.type == "unmatched_answer")
            .first()
        )
        if existing is None:
            db.add(
                ReviewItem(
                    document_id=q.document_id,
                    question_id=q.id,
                    type="unmatched_answer",
                    severity=ReviewSeverity.WARNING,
                    message=f"No answer key entry found for question {q.question_number}.",
                )
            )

    db.commit()
