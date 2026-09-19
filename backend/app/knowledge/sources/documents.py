"""Document importers: Project Gutenberg books, PDFs (with optional OCR for scanned pages), plain text."""

from __future__ import annotations

import hashlib
import io
import logging
import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.knowledge.sources.common import SOURCES_DIR, download
from app.knowledge.store import add_chunks, create_document
from app.knowledge.text import chunk_text

logger = logging.getLogger(__name__)

GUTENBERG_URL = "https://www.gutenberg.org/cache/epub/{id}/pg{id}.txt"
_START = re.compile(r"\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG EBOOK[^\n]*\*\*\*", re.IGNORECASE)
_END = re.compile(r"\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG EBOOK", re.IGNORECASE)
MIN_PAGE_TEXT_CHARS = 40
OCR_PROMPT = (
    "Transcribe all readable text on this page exactly as written, preserving paragraph breaks. "
    "Return only the transcribed text."
)


def fetch_gutenberg(book_id: int, force: bool = False) -> Path:
    return download(GUTENBERG_URL.format(id=book_id), SOURCES_DIR / "gutenberg" / f"pg{book_id}.txt", force)


def strip_gutenberg_boilerplate(raw: str) -> tuple[str, str]:
    """Return (title, body) with the Project Gutenberg license header and footer removed."""
    title_match = re.search(r"^Title:\s*(.+)$", raw, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "Untitled"
    start = _START.search(raw)
    end = _END.search(raw)
    body = raw[start.end() if start else 0:end.start() if end else len(raw)]
    return title, body.strip()


def import_gutenberg(db: Session, book_id: int, path: Path, replace: bool = False) -> dict:
    title, body = strip_gutenberg_boilerplate(path.read_text(encoding="utf-8", errors="replace"))
    document = create_document(
        db, "gutenberg", str(book_id), title,
        license="Public domain in the USA (Project Gutenberg)",
        url=f"https://www.gutenberg.org/ebooks/{book_id}",
        attribution=f"Project Gutenberg eBook #{book_id}",
        replace=replace,
    )
    if document is None:
        logger.info("Gutenberg #%s already imported (use --replace to re-import)", book_id)
        return {"document_id": None, "chunks": 0, "skipped": True}
    count = add_chunks(db, document, chunk_text(body))
    logger.info("Imported '%s': %d chunks", title, count)
    return {"document_id": document.id, "title": title, "chunks": count}


def _ocr_page(page, llm_client) -> str:
    image = page.render(scale=2).to_pil()
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return llm_client.generate(OCR_PROMPT, image_bytes=buffer.getvalue(), cache=True, purpose="pdf_ocr")


def extract_pdf_pages(path: Path, llm_client=None) -> list[tuple[int, str]]:
    """Return [(page_number, text)]. Pages without a text layer are OCR'd when llm_client is given."""
    import pypdfium2 as pdfium

    pages = []
    pdf = pdfium.PdfDocument(str(path))
    try:
        for index in range(len(pdf)):
            page = pdf[index]
            text = page.get_textpage().get_text_range().replace("\r\n", "\n").replace("\r", "\n")
            if len(text.strip()) < MIN_PAGE_TEXT_CHARS and llm_client is not None:
                logger.info("Page %d has no text layer; running OCR", index + 1)
                text = _ocr_page(page, llm_client)
            if text.strip():
                pages.append((index + 1, text))
    finally:
        pdf.close()
    return pages


def import_pdf(
    db: Session, path: Path, title: str, license: str, url: str = "",
    llm_client=None, replace: bool = False,
) -> dict:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    document = create_document(db, "pdf", digest, title, license=license, url=url,
                               attribution=path.name, replace=replace)
    if document is None:
        logger.info("%s already imported (use --replace to re-import)", path.name)
        return {"document_id": None, "chunks": 0, "skipped": True}

    texts, page_numbers = [], []
    for page_number, text in extract_pdf_pages(path, llm_client):
        for chunk in chunk_text(text):
            texts.append(chunk)
            page_numbers.append(page_number)
    count = add_chunks(db, document, texts, page_numbers)
    logger.info("Imported PDF '%s': %d chunks", title, count)
    return {"document_id": document.id, "title": title, "chunks": count}


def import_text_file(db: Session, path: Path, title: str, license: str, url: str = "", replace: bool = False) -> dict:
    content = path.read_text(encoding="utf-8", errors="replace")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    document = create_document(db, "text", digest, title, license=license, url=url,
                               attribution=path.name, replace=replace)
    if document is None:
        return {"document_id": None, "chunks": 0, "skipped": True}
    count = add_chunks(db, document, chunk_text(content))
    return {"document_id": document.id, "title": title, "chunks": count}


EDITORIAL_PATH = Path(__file__).resolve().parents[1] / "data" / "meal_composition.md"


def import_editorial(db: Session, path: Path = EDITORIAL_PATH, replace: bool = True) -> dict:
    """Import the project's own meal-composition notes, one chunk per "## " section."""
    content = path.read_text(encoding="utf-8")
    sections = [s.strip() for s in re.split(r"^## ", content, flags=re.MULTILINE)[1:] if s.strip()]
    texts = []
    for section in sections:
        heading, _, body = section.partition("\n")
        texts.append(f"{heading.strip()}: {' '.join(body.split())}")

    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    document = create_document(
        db, "editorial", "meal_composition", "How dishes are combined (Menuist notes)",
        license="Menuist editorial (MIT)", attribution=f"meal_composition.md@{digest}", replace=replace,
    )
    if document is None:
        return {"document_id": None, "chunks": 0, "skipped": True}
    count = add_chunks(db, document, texts)
    logger.info("Imported editorial notes: %d sections", count)
    return {"document_id": document.id, "chunks": count}
