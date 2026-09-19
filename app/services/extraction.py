"""Rule-based question segmentation and confidence scoring.

Strategy: concatenate page text while keeping a page-number marker at each
boundary, split on question-number patterns (supports "1.", "1)", "Q1.",
"Q.1", "Question 1:" etc.), then split each question block into stem +
options (supports "A)", "A.", "(A)", "a)"). A block that has no number match
at all is treated as a single review-flagged fragment rather than dropped.

This module intentionally has zero external-service dependency so the system
works fully offline; app/services/ai_extraction.py can be layered on top when
GROQ_API_KEY is configured (see extraction pipeline in workers/tasks.py).
"""

import re
from dataclasses import dataclass, field

from app.models.question import QuestionType

# Matches a question-number token at the start of a line, in several common styles:
# "1.", "1)", "Q1.", "Q.1", "Q1)", "Question 1.", "Question 1:"
QUESTION_NUMBER_RE = re.compile(
    r"(?m)^\s*(?:Q(?:uestion)?\.?\s*)?(\d{1,3})[\.\)\:]\s+(?=\S)",
)

# Option line: "A)", "A.", "(A)", "a)" etc. at start of line.
OPTION_RE = re.compile(
    r"(?m)^\s*\(?([A-Da-d])\)?[\.\)]\s+(.*?)(?=\n\s*\(?[A-Da-d]\)?[\.\)]\s+|\Z)",
    re.DOTALL,
)

TRUE_FALSE_RE = re.compile(r"\btrue\s*/\s*false\b", re.IGNORECASE)

PAGE_MARKER_TEMPLATE = "\x00PAGE:{n}\x00"
PAGE_MARKER_RE = re.compile(r"\x00PAGE:(\d+)\x00")


@dataclass
class ExtractedQuestion:
    question_number: str | None
    question_text: str
    options: list[dict] = field(default_factory=list)
    question_type: QuestionType = QuestionType.UNKNOWN
    source_pages: list[int] = field(default_factory=list)
    spans_multiple_pages: bool = False
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)


def build_marked_text(pages: list[tuple[int, str]]) -> str:
    """pages: list of (page_number, text). Inserts an invisible page marker at
    each page boundary so we can recover source_pages after splitting."""
    parts = []
    for page_number, text in pages:
        parts.append(PAGE_MARKER_TEMPLATE.format(n=page_number))
        parts.append(text or "")
    return "\n".join(parts)


def _pages_covered(chunk: str, current_page: int) -> list[int]:
    # A page marker trailing at the very end of a question's block (with only
    # whitespace after it) belongs to the *next* question, not this one -- it
    # only appears here because the marker sits in the gap between the end of
    # this question's content and the next question-number match. Strip any
    # such trailing markers before counting which pages this question spans.
    trimmed = chunk.rstrip()
    while True:
        m = re.search(r"\x00PAGE:(\d+)\x00\s*$", trimmed)
        if not m:
            break
        trimmed = trimmed[: m.start()].rstrip()

    pages = {int(m.group(1)) for m in PAGE_MARKER_RE.finditer(trimmed)}
    pages.add(current_page)
    return sorted(pages)


def _strip_markers(text: str) -> str:
    return PAGE_MARKER_RE.sub("", text).strip()


def _classify_type(stem: str, options: list[dict]) -> QuestionType:
    if TRUE_FALSE_RE.search(stem):
        return QuestionType.TRUE_FALSE
    if len(options) >= 2:
        if re.search(r"select all|choose all|multiple (answers|options)", stem, re.IGNORECASE):
            return QuestionType.MCQ_MULTI
        return QuestionType.MCQ_SINGLE
    if not options:
        return QuestionType.SHORT_ANSWER
    return QuestionType.UNKNOWN


def _score_confidence(q_number: str | None, stem: str, options: list[dict], spans_pages: bool, low_ocr: bool) -> tuple[float, list[str]]:
    score = 1.0
    warnings: list[str] = []

    if not q_number:
        score -= 0.3
        warnings.append("missing_question_number")

    stem_len = len(stem.strip())
    if stem_len < 5:
        score -= 0.4
        warnings.append("empty_or_too_short_question_text")
    elif stem_len < 15:
        score -= 0.15
        warnings.append("very_short_question_text")

    if options and len(options) < 2:
        score -= 0.15
        warnings.append("only_one_option_detected")

    if spans_pages:
        score -= 0.05
        warnings.append("spans_multiple_pages")

    if low_ocr:
        score -= 0.2
        warnings.append("low_ocr_confidence_source")

    return max(0.0, min(1.0, score)), warnings


def parse_options(block: str) -> tuple[str, list[dict]]:
    matches = list(OPTION_RE.finditer(block))
    if not matches:
        return block.strip(), []
    stem = block[: matches[0].start()].strip()
    options = []
    for m in matches:
        label = m.group(1).upper()
        text = re.sub(r"\s+", " ", m.group(2)).strip()
        if text:
            options.append({"label": label, "text": text})
    return stem, options


def extract_questions(pages: list[tuple[int, str]], avg_ocr_confidence: float | None) -> list[ExtractedQuestion]:
    """pages: [(page_number, page_text), ...] in order. Returns ExtractedQuestion list."""
    marked = build_marked_text(pages)
    low_ocr = avg_ocr_confidence is not None and avg_ocr_confidence < 0.6

    matches = list(QUESTION_NUMBER_RE.finditer(marked))
    results: list[ExtractedQuestion] = []

    if not matches:
        cleaned = _strip_markers(marked)
        if cleaned:
            stem, options = parse_options(cleaned)
            conf, warnings = _score_confidence(None, stem, options, spans_pages=len(pages) > 1, low_ocr=low_ocr)
            results.append(
                ExtractedQuestion(
                    question_number=None,
                    question_text=stem,
                    options=options,
                    question_type=_classify_type(stem, options),
                    source_pages=[p for p, _ in pages],
                    spans_multiple_pages=len(pages) > 1,
                    confidence=conf,
                    warnings=warnings + ["no_question_numbers_detected_in_document"],
                )
            )
        return results

    for idx, m in enumerate(matches):
        q_number = m.group(1)
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(marked)
        raw_block = marked[start:end]

        # Determine current page: last page marker seen before this match.
        preceding = marked[: m.start()]
        page_hits = PAGE_MARKER_RE.findall(preceding)
        current_page = int(page_hits[-1]) if page_hits else pages[0][0]

        source_pages = _pages_covered(raw_block, current_page)
        spans_multiple = len(source_pages) > 1

        cleaned_block = _strip_markers(raw_block)
        stem, options = parse_options(cleaned_block)
        q_type = _classify_type(stem, options)
        conf, warnings = _score_confidence(q_number, stem, options, spans_multiple, low_ocr)

        results.append(
            ExtractedQuestion(
                question_number=q_number,
                question_text=stem,
                options=options,
                question_type=q_type,
                source_pages=source_pages,
                spans_multiple_pages=spans_multiple,
                confidence=conf,
                warnings=warnings,
            )
        )

    return results
