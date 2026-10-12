"""文件解析：把上传的简历（PDF / DOCX / TXT / MD）解析为纯文本。"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Union

_SUPPORTED = {".pdf", ".docx", ".txt", ".md", ".text"}


def parse_bytes(filename: str, data: bytes) -> str:
    """解析上传文件字节流为文本（用于 Streamlit file_uploader）。"""
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    if suffix == ".docx":
        import docx
        return _docx_to_text(docx.Document(BytesIO(data)))
    if suffix in (".txt", ".md", ".text", ""):
        return data.decode("utf-8", errors="ignore").strip()
    raise ValueError(f"不支持的文件类型：{suffix}（支持 {', '.join(sorted(_SUPPORTED))}）")


def parse_file(path: Union[str, Path]) -> str:
    """解析本地文件路径为文本。"""
    p = Path(path)
    return parse_bytes(p.name, p.read_bytes())


def _docx_to_text(doc) -> str:
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" ".join(cell.text for cell in row.cells))
    return "\n".join(parts).strip()
