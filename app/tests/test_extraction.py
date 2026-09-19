from app.models.question import QuestionType
from app.services.extraction import extract_questions, parse_options


def test_extract_simple_mcq_single_page():
    pages = [
        (1, "1. What is 2+2?\nA) 3\nB) 4\nC) 5\nD) 6\n\n2. What is the capital of Japan?\nA) Tokyo\nB) Kyoto"),
    ]
    questions = extract_questions(pages, avg_ocr_confidence=None)

    assert len(questions) == 2
    q1 = questions[0]
    assert q1.question_number == "1"
    assert "2+2" in q1.question_text
    assert [o["label"] for o in q1.options] == ["A", "B", "C", "D"]
    assert q1.question_type == QuestionType.MCQ_SINGLE
    assert q1.confidence > 0.7
    assert q1.source_pages == [1]


def test_question_spanning_multiple_pages_is_flagged():
    pages = [
        (1, "5. A long question that starts here and continues"),
        (2, "onto the next page before the options appear.\nA) One\nB) Two"),
    ]
    questions = extract_questions(pages, avg_ocr_confidence=None)

    assert len(questions) == 1
    q = questions[0]
    assert q.spans_multiple_pages is True
    assert q.source_pages == [1, 2]
    assert "spans_multiple_pages" in q.warnings


def test_missing_question_number_lowers_confidence_but_is_not_dropped():
    pages = [(1, "Explain briefly why the sky is blue during the day.")]
    questions = extract_questions(pages, avg_ocr_confidence=None)

    assert len(questions) == 1
    assert questions[0].question_number is None
    assert questions[0].confidence < 1.0
    assert "missing_question_number" in questions[0].warnings


def test_low_ocr_confidence_penalizes_score():
    pages = [(1, "1. What is the boiling point of water in Celsius?\nA) 90\nB) 100\nC) 110\nD) 120")]
    high_conf = extract_questions(pages, avg_ocr_confidence=0.95)[0]
    low_conf = extract_questions(pages, avg_ocr_confidence=0.3)[0]

    assert low_conf.confidence < high_conf.confidence
    assert "low_ocr_confidence_source" in low_conf.warnings


def test_trailing_page_marker_not_falsely_attributed_to_prior_question():
    """A question fully contained on page 1 should not be marked as spanning
    onto page 2 just because the next page's boundary marker falls in the gap
    between this question's content and the next question's number."""
    pages = [
        (1, "4. Fully on page one?\nA) x\nB) y"),
        (2, "5. Starts fresh on page two.\nA) x\nB) y"),
    ]
    questions = extract_questions(pages, avg_ocr_confidence=None)
    q4 = next(q for q in questions if q.question_number == "4")
    assert q4.source_pages == [1]
    assert q4.spans_multiple_pages is False


def test_true_false_type_detected():
    pages = [(1, "6. The Great Wall of China is visible from space.\nTrue / False")]
    q = extract_questions(pages, avg_ocr_confidence=None)[0]
    assert q.question_type == QuestionType.TRUE_FALSE


def test_short_answer_type_when_no_options():
    pages = [(1, "7. Explain briefly why the sky appears blue during the day in some detail.")]
    q = extract_questions(pages, avg_ocr_confidence=None)[0]
    assert q.question_type == QuestionType.SHORT_ANSWER
    assert q.options == []


def test_no_question_numbers_at_all_yields_single_review_fragment():
    pages = [(1, "This page has no discernible question numbering at all in it.")]
    questions = extract_questions(pages, avg_ocr_confidence=None)
    assert len(questions) == 1
    assert "no_question_numbers_detected_in_document" in questions[0].warnings


def test_parse_options_handles_parenthesized_labels():
    stem, options = parse_options("What color is the sky?\n(A) Red\n(B) Blue\n(C) Green")
    assert stem == "What color is the sky?"
    assert options == [
        {"label": "A", "text": "Red"},
        {"label": "B", "text": "Blue"},
        {"label": "C", "text": "Green"},
    ]
