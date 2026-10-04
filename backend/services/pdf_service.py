"""
FriendOS PDF Service – extracts text from uploaded PDFs using PyMuPDF.

Handles:
- Page-by-page text extraction with page numbers
- File type validation
- Empty/scanned PDF detection
- Size limits
- Graceful error handling for malformed PDFs
"""

from typing import BinaryIO

import fitz  # PyMuPDF


# ── Constants ─────────────────────────────────────────────────────────

MAX_PDF_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_PAGES = 200


class PDFExtractionError(Exception):
    """Raised when PDF processing fails in an expected way."""
    pass


class PDFExtractionResult:
    """Holds the output of a successful PDF text extraction."""

    def __init__(self, text: str, page_count: int, pages: list[dict]):
        self.text = text              # full concatenated text
        self.page_count = page_count  # total pages in the PDF
        self.pages = pages            # [{"page": 1, "text": "..."}, ...]


def extract_text_from_pdf(
    file: BinaryIO,
    filename: str,
    max_size: int = MAX_PDF_SIZE_BYTES,
) -> PDFExtractionResult:
    """
    Extract selectable text from an in-memory PDF file.

    Parameters
    ----------
    file : BinaryIO
        A file-like object (e.g. from FastAPI's UploadFile).
    filename : str
        Original filename – used for type checking.
    max_size : int
        Maximum allowed file size in bytes.

    Returns
    -------
    PDFExtractionResult

    Raises
    ------
    PDFExtractionError
        On invalid file type, size limit exceeded, malformed PDF,
        or empty/scanned PDF with no extractable text.
    """
    # ── Validate file extension ───────────────────────────────────────
    if not filename.lower().endswith(".pdf"):
        raise PDFExtractionError(
            f"Unsupported file type: '{filename}'. Only PDF files are accepted."
        )

    # ── Read bytes and check size ─────────────────────────────────────
    try:
        pdf_bytes = file.read()
    except Exception as exc:
        raise PDFExtractionError(f"Failed to read uploaded file: {exc}")

    if len(pdf_bytes) == 0:
        raise PDFExtractionError("Uploaded file is empty.")

    if len(pdf_bytes) > max_size:
        size_mb = len(pdf_bytes) / (1024 * 1024)
        limit_mb = max_size / (1024 * 1024)
        raise PDFExtractionError(
            f"PDF is too large ({size_mb:.1f} MB). Maximum allowed size is {limit_mb:.0f} MB."
        )

    # ── Open with PyMuPDF ─────────────────────────────────────────────
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise PDFExtractionError(f"Failed to open PDF: {exc}")

    page_count = len(doc)
    if page_count == 0:
        doc.close()
        raise PDFExtractionError("PDF has no pages.")

    if page_count > MAX_PAGES:
        doc.close()
        raise PDFExtractionError(
            f"PDF has {page_count} pages, exceeding the limit of {MAX_PAGES}."
        )

    # ── Extract text page by page ─────────────────────────────────────
    pages: list[dict] = []
    all_text_parts: list[str] = []

    try:
        for i, page in enumerate(doc):
            page_text = page.get_text("text").strip()
            pages.append({"page": i + 1, "text": page_text})
            if page_text:
                all_text_parts.append(f"[Page {i + 1}]\n{page_text}")
    except Exception as exc:
        doc.close()
        raise PDFExtractionError(f"Error extracting text from PDF: {exc}")
    finally:
        doc.close()

    full_text = "\n\n".join(all_text_parts)

    if not full_text.strip():
        raise PDFExtractionError(
            "No extractable text found in PDF. "
            "The document may be scanned/image-based. OCR is not supported yet."
        )

    return PDFExtractionResult(
        text=full_text,
        page_count=page_count,
        pages=pages,
    )
