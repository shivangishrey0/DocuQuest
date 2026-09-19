"""Generates sample input documents for demonstrating DocuQuest end to end.

Produces, into sample_data/:
  - question_paper_digital.pdf   : clean digitally-generated PDF, 2 pages,
                                    multiple questions per page, one question
                                    spanning the page break, mixed numbering.
  - answer_key.pdf               : a separate document with the answers for
                                    question_paper_digital.pdf (to demonstrate
                                    multi-document grouping).
  - scanned_lowquality.png       : a rendered, rotated, noised version of a
                                    question page to simulate a poor scan.
  - unsupported.txt              : a plain-text file to demonstrate rejection
                                    of unsupported file types.

Run with: python -m scripts.generate_samples
"""

import io
import random

from PIL import Image, ImageDraw, ImageFilter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

OUT_DIR_NAME = "sample_data"


def _wrap(text: str, width: int = 95) -> list[str]:
    words = text.split()
    lines, current = [], ""
    for w in words:
        if len(current) + len(w) + 1 > width:
            lines.append(current)
            current = w
        else:
            current = f"{current} {w}".strip()
    if current:
        lines.append(current)
    return lines


def generate_question_paper(path: str):
    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4
    y = height - 2 * cm

    def line(text, size=11, dy=0.6 * cm, font="Helvetica"):
        nonlocal y
        c.setFont(font, size)
        c.drawString(2 * cm, y, text)
        y -= dy

    line("SAMPLE APTITUDE TEST — SET A", size=16, font="Helvetica-Bold", dy=1.2 * cm)
    line("Instructions: Choose the single best answer for each question.", size=10, dy=1 * cm)

    questions = [
        ("1", "What is the capital of France?", ["Paris", "Berlin", "Madrid", "Rome"]),
        ("2", "Which data structure uses FIFO order?", ["Stack", "Queue", "Tree", "Graph"]),
        ("3", "What does CPU stand for?", ["Central Processing Unit", "Computer Personal Unit", "Central Program Utility", "Core Processing Unit"]),
        ("4", "2 + 2 * 2 equals?", ["6", "8", "4", "10"]),
    ]
    for num, stem, options in questions:
        line(f"{num}. {stem}")
        for i, opt in enumerate(options):
            label = chr(65 + i)
            line(f"    {label}) {opt}", size=10, dy=0.5 * cm)
        y -= 0.3 * cm

    # Force a page break right before question 5 so it deliberately starts on
    # page 1 and its options land on page 2 -- demonstrates multi-page handling.
    c.showPage()
    y = height - 2 * cm

    long_stem = (
        "5. A train travels from City A to City B, a distance of 300 km, at an average "
        "speed of 60 km/h. Midway through the journey it stops for 45 minutes at a "
        "station due to signal failure, then continues the rest of the journey at a "
        "reduced average speed of 50 km/h because of the delay. Given this information, "
        "what is the total time taken, in hours and minutes, for the train to complete "
        "the entire journey from City A to City B, including the stoppage time?"
    )
    wrapped = _wrap(long_stem, width=90)
    # Print only the stem on page 1, leaving no room for options, then force the
    # page break before printing the option list on page 2.
    for wline in wrapped:
        line(wline, dy=0.5 * cm)
    c.showPage()
    y = height - 2 * cm
    for i, opt in enumerate(["4 hours 45 minutes", "5 hours 15 minutes", "5 hours 45 minutes", "6 hours 0 minutes"]):
        label = chr(65 + i)
        line(f"    {label}) {opt}", size=10, dy=0.5 * cm)

    y -= 0.5 * cm
    line("6. The Great Wall of China is visible from space with the naked eye.", dy=0.5 * cm)
    line("    True / False", size=10, dy=0.5 * cm)

    y -= 0.5 * cm
    line("7 Explain briefly why the sky appears blue during the day.", dy=0.5 * cm)

    c.showPage()
    c.save()


def generate_answer_key(path: str):
    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4
    y = height - 2 * cm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2 * cm, y, "ANSWER KEY — SAMPLE APTITUDE TEST SET A")
    y -= 1 * cm
    c.setFont("Helvetica", 11)
    answers = [("1", "A"), ("2", "B"), ("3", "A"), ("4", "B"), ("5", "C")]
    for num, ans in answers:
        c.drawString(2 * cm, y, f"{num}. {ans}")
        y -= 0.6 * cm
    # Note: 6 and 7 intentionally omitted to demonstrate "unmatched answer" handling.
    c.showPage()
    c.save()


def generate_scanned_lowquality(path: str):
    """Renders a small question block as an image, then rotates and adds noise/blur
    to simulate a poor-quality phone-camera scan."""
    img = Image.new("L", (1000, 700), color=255)
    draw = ImageDraw.Draw(img)
    text_lines = [
        "8. Which gas do plants absorb from the atmosphere",
        "   for photosynthesis?",
        "   A) Oxygen",
        "   B) Carbon Dioxide",
        "   C) Nitrogen",
        "   D) Hydrogen",
    ]
    y = 60
    for line_text in text_lines:
        draw.text((40, y), line_text, fill=0)
        y += 60

    # Slight rotation to simulate a crooked scan (small enough that Tesseract's
    # orientation detector won't misfire and flip the page upside down).
    img = img.rotate(3, expand=True, fillcolor=255)

    # Add light speckle noise -- enough to degrade OCR confidence without making
    # the text fully unrecoverable, so this sample demonstrates a *partial*/review
    # extraction rather than a total failure.
    pixels = img.load()
    for _ in range(4000):
        x = random.randint(0, img.width - 1)
        yy = random.randint(0, img.height - 1)
        pixels[x, yy] = random.choice([0, 255])

    img = img.filter(ImageFilter.GaussianBlur(radius=0.6))
    img.convert("RGB").save(path, "PNG")


def generate_unsupported(path: str):
    with open(path, "w") as f:
        f.write("This is a plain text file used to demonstrate rejection of unsupported uploads.\n")


def main():
    import os

    os.makedirs(OUT_DIR_NAME, exist_ok=True)
    generate_question_paper(os.path.join(OUT_DIR_NAME, "question_paper_digital.pdf"))
    generate_answer_key(os.path.join(OUT_DIR_NAME, "answer_key.pdf"))
    generate_scanned_lowquality(os.path.join(OUT_DIR_NAME, "scanned_lowquality.png"))
    generate_unsupported(os.path.join(OUT_DIR_NAME, "unsupported.txt"))
    print(f"Sample documents written to ./{OUT_DIR_NAME}/")


if __name__ == "__main__":
    main()
