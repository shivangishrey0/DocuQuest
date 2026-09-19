"""Answer-key detection and parsing.

Handles answer keys that are:
  - a trailing section of the same document ("Answer Key" / "Answers" heading)
  - a leading section
  - a completely separate document in the same DocumentGroup

Recognizes common line formats:
  "1. A"        "1) B"        "1 - C"        "1: D"
  "1. A, 2. B, 3. C" (comma-separated on one line)
  "Q1 - A"      "1.A"
"""

import re
from dataclasses import dataclass

HEADING_RE = re.compile(
    r"(?im)^\s*(answer\s*key|answers?|key|solutions?)\s*[:\-]?\s*$"
)

# "1. A" / "1) B" / "1 - C" / "1: D" / "Q1 - A" / "1.A" (no space)
ENTRY_RE = re.compile(
    r"(?:Q\.?\s*)?(\d{1,3})\s*[\.\)\-:]\s*([A-Da-d])(?:\b|(?=[\s,;]))"
)


@dataclass
class AnswerKeyRow:
    question_number: str
    answer_text: str
    raw_line: str
    source_page: int | None
    confidence: float


def find_answer_key_section(pages: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Returns the subset of pages (page_number, text) that look like an answer-key
    section, based on a heading match. If no explicit heading is found but the page
    text is dominated by short "<num> <letter>" patterns, it's still considered."""
    heading_page = None
    for page_number, text in pages:
        if HEADING_RE.search(text or ""):
            heading_page = page_number
            break

    if heading_page is not None:
        return [(p, t) for p, t in pages if p >= heading_page]

    # Heuristic fallback: a page where >50% of non-blank lines match ENTRY_RE
    # is very likely an answer key even without an explicit heading.
    candidates = []
    for page_number, text in pages:
        lines = [l for l in (text or "").splitlines() if l.strip()]
        if not lines:
            continue
        hits = sum(1 for l in lines if ENTRY_RE.search(l))
        if len(lines) >= 3 and hits / len(lines) >= 0.5:
            candidates.append((page_number, text))
    return candidates


def parse_answer_key(pages: list[tuple[int, str]], base_confidence: float = 0.85) -> list[AnswerKeyRow]:
    rows: list[AnswerKeyRow] = []
    seen_numbers: set[str] = set()
    for page_number, text in pages:
        for line in (text or "").splitlines():
            for m in ENTRY_RE.finditer(line):
                q_num, ans = m.group(1), m.group(2).upper()
                if q_num in seen_numbers:
                    continue
                seen_numbers.add(q_num)
                rows.append(
                    AnswerKeyRow(
                        question_number=q_num,
                        answer_text=ans,
                        raw_line=line.strip(),
                        source_page=page_number,
                        confidence=base_confidence,
                    )
                )
    return rows
