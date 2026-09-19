"""Text extraction layer: pulls page-level text out of digital PDFs, scanned PDFs,
and standalone images, normalizing everything into a common PageResult shape so the
question-extraction engine downstream never needs to know which path produced it.
"""

from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image, ImageOps
from pdf2image import convert_from_path

from app.config import settings

if settings.TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

MIN_TEXT_LAYER_CHARS_PER_PAGE = 20  # below this, a PDF page is treated as scanned/image-only


@dataclass
class PageResult:
    page_number: int  # 1-indexed
    text: str
    extraction_method: str  # "text_layer" | "ocr"
    ocr_confidence: float | None
    image_path: str | None
    rotation_applied: int = 0


def _detect_and_fix_rotation(img: Image.Image) -> tuple[Image.Image, int]:
    """Uses Tesseract's orientation detection to auto-rotate skewed/rotated scans."""
    try:
        osd = pytesseract.image_to_osd(img)
        rotate = 0
        for line in osd.splitlines():
            if line.startswith("Rotate:"):
                rotate = int(line.split(":")[1].strip())
                break
        if rotate and rotate != 0:
            img = img.rotate(-rotate, expand=True)
        return img, rotate
    except Exception:
        return img, 0


def _ocr_image(img: Image.Image) -> tuple[str, float]:
    img = ImageOps.exif_transpose(img)
    img = img.convert("L")  # grayscale improves OCR on low-quality scans
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    words = []
    confidences = []
    for i, word in enumerate(data["text"]):
        if word.strip():
            words.append(word)
            conf = data["conf"][i]
            try:
                conf_f = float(conf)
                if conf_f >= 0:
                    confidences.append(conf_f)
            except (ValueError, TypeError):
                pass
    text = pytesseract.image_to_string(img)
    avg_conf = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.0
    return text, avg_conf


def process_pdf(pdf_path: str, image_out_dir: Path) -> list[PageResult]:
    results: list[PageResult] = []
    doc = fitz.open(pdf_path)
    try:
        for i in range(len(doc)):
            page = doc[i]
            page_number = i + 1
            text = page.get_text("text") or ""

            if len(text.strip()) >= MIN_TEXT_LAYER_CHARS_PER_PAGE:
                results.append(
                    PageResult(
                        page_number=page_number,
                        text=text,
                        extraction_method="text_layer",
                        ocr_confidence=None,
                        image_path=None,
                    )
                )
                continue

            # Fall back to OCR: render the page to an image first.
            pix = page.get_pixmap(dpi=250)
            img_path = image_out_dir / f"page_{page_number:03d}.png"
            pix.save(str(img_path))
            img = Image.open(img_path)
            img, rotation = _detect_and_fix_rotation(img)
            if rotation:
                img.save(img_path)
            ocr_text, conf = _ocr_image(img)
            results.append(
                PageResult(
                    page_number=page_number,
                    text=ocr_text,
                    extraction_method="ocr",
                    ocr_confidence=conf,
                    image_path=str(img_path),
                    rotation_applied=rotation,
                )
            )
    finally:
        doc.close()
    return results


def process_image(image_path: str, image_out_dir: Path) -> list[PageResult]:
    img = Image.open(image_path)
    img, rotation = _detect_and_fix_rotation(img)
    out_path = image_out_dir / "page_001.png"
    img.save(out_path)
    text, conf = _ocr_image(img)
    return [
        PageResult(
            page_number=1,
            text=text,
            extraction_method="ocr",
            ocr_confidence=conf,
            image_path=str(out_path),
            rotation_applied=rotation,
        )
    ]


def extract_pages(file_path: str, file_type: str, image_out_dir: Path) -> list[PageResult]:
    if file_type == "pdf":
        return process_pdf(file_path, image_out_dir)
    return process_image(file_path, image_out_dir)
