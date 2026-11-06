"""Text extraction from uploaded files: TXT, PDF (PyMuPDF), DOCX (python-docx) and images (OCR)."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Tuple

ALLOWED_EXTENSIONS = {".txt": "txt", ".pdf": "pdf", ".docx": "docx",
                      ".png": "image", ".jpg": "image", ".jpeg": "image"}
MAX_PDF_PAGES = 100
_WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"


class ExtractionError(Exception):
    """Raised with a user-friendly message when a file cannot be read."""


def signature_ok(ext: str, head: bytes) -> bool:
    """Check the file's first bytes match its claimed type (extension alone can be faked)."""
    if ext == ".pdf":
        return head.startswith(b"%PDF")
    if ext == ".docx":
        return head.startswith(b"PK")
    if ext == ".png":
        return head.startswith(b"\x89PNG")
    if ext in (".jpg", ".jpeg"):
        return head.startswith(b"\xff\xd8")
    if ext == ".txt":
        return b"\x00" not in head  # reject binary
    return False


def _ocr_image(img, ocr_enabled: bool) -> Tuple[str, float | None]:
    if not ocr_enabled:
        raise ExtractionError("OCR is disabled on this server, so image text cannot be read.")
    try:
        import pytesseract
        from app.core.config import get_settings
        if get_settings().TESSERACT_CMD:
            pytesseract.pytesseract.tesseract_cmd = get_settings().TESSERACT_CMD
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    except Exception as exc:  # TesseractNotFoundError and friends
        if exc.__class__.__name__ == "TesseractNotFoundError":
            raise ExtractionError("The OCR engine (Tesseract) is not installed on this server.") from exc
        raise ExtractionError("The image could not be processed by the OCR engine.") from exc
    words, confs = [], []
    for txt, conf in zip(data["text"], data["conf"]):
        if txt.strip():
            words.append(txt)
            try:
                c = float(conf)
                if c >= 0:
                    confs.append(c)
            except ValueError:
                pass
    # rebuild lines to keep reading order
    lines = {}
    for i, txt in enumerate(data["text"]):
        if txt.strip():
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines.setdefault(key, []).append(txt)
    text = "\n".join(" ".join(v) for _, v in sorted(lines.items()))
    return text, (sum(confs) / len(confs) if confs else None)


def extract_text(path: Path, ext: str, ocr_enabled: bool = True) -> Tuple[str, dict]:
    meta: dict = {"warnings": []}
    kind = ALLOWED_EXTENSIONS.get(ext)
    if kind is None:
        raise ExtractionError("Unsupported file type.")

    if kind == "txt":
        raw = path.read_bytes()
        for enc in ("utf-8-sig", "utf-16", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ExtractionError("The text file could not be decoded.")

    elif kind == "pdf":
        import pymupdf
        try:
            doc = pymupdf.open(str(path))
        except Exception as exc:
            raise ExtractionError("The PDF file is damaged or cannot be opened.") from exc
        with doc:
            if doc.needs_pass:
                raise ExtractionError("Password-protected PDFs are not supported.")
            if doc.page_count > MAX_PDF_PAGES:
                raise ExtractionError(f"PDF has too many pages (limit {MAX_PDF_PAGES}).")
            parts, ocr_pages = [], 0
            for page in doc:
                t = page.get_text("text").strip()
                if not t and ocr_enabled:
                    try:
                        from PIL import Image
                        pix = page.get_pixmap(dpi=150)
                        img = Image.open(io.BytesIO(pix.tobytes("png")))
                        t, _ = _ocr_image(img, True)
                        ocr_pages += 1
                    except ExtractionError as exc:
                        meta["warnings"].append(f"Page {page.number + 1} has no text layer; {exc}")
                parts.append(t)
            meta["pages"] = doc.page_count
            if ocr_pages:
                meta["ocr_pages"] = ocr_pages
            text = "\n\n".join(p for p in parts if p)

    elif kind == "docx":
        import docx
        try:
            d = docx.Document(str(path))
        except Exception as exc:
            raise ExtractionError("The Word document is damaged or cannot be opened.") from exc
        parts = [p.text for p in d.paragraphs if p.text.strip()]
        for table in d.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    parts.append(" | ".join(cells))
        text = "\n".join(parts)
        props = list(d.element.body.iter(f"{{{_WP_NS}}}docPr"))
        meta["images_total"] = len(props)
        meta["images_without_alt"] = sum(1 for e in props if not (e.get("descr") or "").strip())

    else:  # image
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = 50_000_000
        try:
            img = Image.open(path)
            img.load()
        except Exception as exc:
            raise ExtractionError("The image file is damaged or cannot be opened.") from exc
        text, conf = _ocr_image(img, ocr_enabled)
        if conf is not None:
            meta["ocr_confidence"] = round(conf, 1)
            if conf < 60:
                meta["warnings"].append("OCR confidence is low; text may be misread. Check the extracted text.")

    text = text.strip()
    if not text:
        raise ExtractionError("No readable text was found in the file.")
    return text, meta
