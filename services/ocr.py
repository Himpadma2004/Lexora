"""
services/ocr.py
PDF and image text extraction helpers for Lexora Practice Mode.

Pipeline:
  - PDFs: PyMuPDF text extraction first, OCR fallback for scanned pages
  - Images: EasyOCR with lightweight PIL/NumPy preprocessing
  - Optional OpenCV acceleration when the package is installed
"""

from __future__ import annotations

import io
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import fitz  # PyMuPDF
import numpy as np
from PIL import Image, ImageEnhance, ImageOps

try:  # Optional: use OpenCV preprocessing when available.
    import cv2  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    cv2 = None

import easyocr


def _normalize_text(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


@lru_cache(maxsize=1)
def _get_reader() -> easyocr.Reader:
    """Create one shared EasyOCR reader for the process."""
    return easyocr.Reader(["en"], gpu=False)


def _preprocess_image(image: Image.Image) -> np.ndarray:
    """Lightweight preprocessing to improve OCR quality."""
    image = image.convert("RGB")
    image = ImageOps.autocontrast(image)
    image = ImageEnhance.Contrast(image).enhance(1.6)
    image = ImageEnhance.Sharpness(image).enhance(1.35)

    if min(image.size) < 1200:
        image = image.resize((image.width * 2, image.height * 2))

    if cv2 is not None:
        arr = np.array(image)
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        gray = cv2.bilateralFilter(gray, 7, 75, 75)
        return cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            11,
        )

    gray = ImageOps.grayscale(image)
    gray = ImageEnhance.Contrast(gray).enhance(1.7)
    return np.array(gray)


def _ocr_image(image: Image.Image) -> str:
    reader = _get_reader()
    processed = _preprocess_image(image)
    lines = reader.readtext(processed, detail=0, paragraph=True)
    return _normalize_text("\n".join(lines))


def extract_text_from_image_bytes(image_bytes: bytes) -> str:
    """Extract text from a JPEG/PNG image."""
    with Image.open(io.BytesIO(image_bytes)) as image:
        return _ocr_image(image)


def extract_text_from_pdf_bytes(pdf_bytes: bytes, filename: str = "document.pdf") -> str:
    """
    Extract text from a PDF.

    Digital PDFs use native text extraction first. For pages that look like
    scans, the page is rendered and sent through EasyOCR.
    """
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    segments: list[str] = []

    for page_index, page in enumerate(document, start=1):
        text = _normalize_text(page.get_text("text"))
        if len(text) >= 40:
            segments.append(f"[Page {page_index}]\n{text}")
            continue

        pixmap = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
        image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
        ocr_text = _ocr_image(image)
        if ocr_text:
            segments.append(f"[Page {page_index}]\n{ocr_text}")

    return _normalize_text("\n\n".join(segments))


def extract_text_from_file(file_name: str, file_bytes: bytes, mime_type: str | None = None) -> str:
    """Dispatch a single file to the correct extractor."""
    lower_name = file_name.lower()
    is_pdf = lower_name.endswith(".pdf") or (mime_type or "").lower() == "application/pdf"
    if is_pdf:
        return extract_text_from_pdf_bytes(file_bytes, filename=file_name)
    return extract_text_from_image_bytes(file_bytes)


def extract_text_from_sources(sources: Iterable[dict]) -> str:
    """
    Extract and concatenate text from a mixed set of PDF/image sources.

    Each source dictionary may contain: name, bytes, mime_type.
    """
    parts: list[str] = []
    for source in sources:
        name = source.get("name", "source")
        data = source.get("bytes", b"")
        mime_type = source.get("mime_type")
        if not data:
            continue
        text = extract_text_from_file(name, data, mime_type=mime_type)
        if text:
            parts.append(f"### {name}\n{text}")

    return _normalize_text("\n\n".join(parts))
