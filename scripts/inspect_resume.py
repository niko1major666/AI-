"""检查简历 PDF：提取文本层，输出统计与全文到 UTF-8 文件。"""
import sys
from pathlib import Path

from pypdf import PdfReader

pdf_path = sys.argv[1]
out_path = sys.argv[2]

reader = PdfReader(pdf_path)
pages = [p.extract_text() or "" for p in reader.pages]
text = "\n".join(pages)

Path(out_path).write_text(
    f"pages={len(reader.pages)}\n"
    f"total_len={len(text)}\n"
    f"per_page_len={[len(x) for x in pages]}\n"
    f"{'-' * 40}\n{text}",
    encoding="utf-8",
)
print("done pages", len(reader.pages), "total_len", len(text))
