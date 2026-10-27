import fitz  # PyMuPDF

MAX_PAPER_CHARS = 80000


def extract_text(path):
    """Return the PDF's text, truncated to MAX_PAPER_CHARS."""
    with fitz.open(path) as doc:
        text = "".join(page.get_text() for page in doc)
    return text[:MAX_PAPER_CHARS]
