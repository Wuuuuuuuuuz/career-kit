"""简历文件解析——支持 PDF、DOCX、Markdown、TXT。"""

from __future__ import annotations

from pathlib import Path

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".md", ".txt", ".markdown"}


def extract_text(file_path: str) -> str:
    """Extract text from a resume file.

    Args:
        file_path: Absolute path to the resume file.

    Returns:
        Extracted plain text content.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: If file extension is not supported.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在：{file_path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"不支持的文件格式：{ext}。支持的格式：{', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if ext == ".pdf":
        return _extract_pdf(path)
    elif ext == ".docx":
        return _extract_docx(path)
    else:
        return _extract_text(path)


def _extract_pdf(path: Path) -> str:
    import pdfplumber

    pages_text = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
    return "\n\n".join(pages_text)


def _extract_docx(path: Path) -> str:
    from docx import Document

    doc = Document(path)
    return "\n".join(para.text for para in doc.paragraphs if para.text.strip())


def _extract_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")
