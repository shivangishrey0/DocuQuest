from app.services.answer_key import find_answer_key_section, parse_answer_key


def test_finds_answer_key_by_heading():
    pages = [
        (1, "1. Question one\nA) x\nB) y"),
        (2, "Answer Key\n1. A\n2. B\n3. C"),
    ]
    section = find_answer_key_section(pages)
    assert [p for p, _ in section] == [2]


def test_finds_answer_key_by_heuristic_when_no_heading():
    pages = [
        (1, "1. Question one\nA) x\nB) y"),
        (2, "1. A\n2. B\n3. C\n4. D\n5. A"),
    ]
    section = find_answer_key_section(pages)
    assert [p for p, _ in section] == [2]


def test_no_false_positive_on_normal_question_page():
    pages = [(1, "1. What is 2+2?\nA) 3\nB) 4\nC) 5\nD) 6")]
    section = find_answer_key_section(pages)
    assert section == []


def test_parse_answer_key_extracts_rows_and_dedupes():
    pages = [(2, "1. A\n2) B\n3 - C\n1. A (duplicate, ignored)")]
    rows = parse_answer_key(pages)
    assert [(r.question_number, r.answer_text) for r in rows] == [("1", "A"), ("2", "B"), ("3", "C")]
    assert all(r.source_page == 2 for r in rows)
