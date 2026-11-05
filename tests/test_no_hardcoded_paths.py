"""硬化回归：`src/` 与 `scripts/` 下不得出现「本机特定」的绝对路径。

只扫代码目录，不扫 `docs/` / `memory-bank/` / `tests/`：

- 文档里出现路径示例是合理的；
- `tests/test_script_paths.py` 本身必须写出被禁字符串来构造正则。

拦截对象（不是所有盘符，只针对会绑死机器的写法）：
- `X:\\Users\\...` / `X:/Users/...`
- `X:\\ai-skill-gap` / `X:/ai-skill-gap`
- `/home/<user>/` / `/Users/<user>/`

正确写法：`Path(__file__).resolve().parents[1]`、`$PSScriptRoot`、`Get-Command`。
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ("src", "scripts")
TEXT_SUFFIXES = {".py", ".ps1", ".psm1", ".sh", ".bat", ".cmd", ".toml", ".yaml", ".yml"}

# `\b` 保证不会把 `https://` 里的 `s:` 当成盘符
_MACHINE_PATH = re.compile(
    r"\b[A-Za-z]:[\\/]{1,2}(?:Users|ai-skill-gap)\b"
    r"|/home/[A-Za-z0-9._-]+/"
    r"|/Users/[A-Za-z0-9._-]+/"
)

_DRIVE_LITERAL = re.compile(r"\b[A-Za-z]:[\\/]{1,2}[A-Za-z0-9._$-]")


def _iter_code_files():
    for dirname in SCAN_DIRS:
        base = ROOT / dirname
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
                yield path


def _iter_lines(path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    for lineno, line in enumerate(text.splitlines(), 1):
        yield lineno, line


def test_no_machine_specific_paths_in_code():
    """代码里不允许出现绑死本机的路径（含用户目录 / 项目盘符）。"""
    hits = [
        f"{path.relative_to(ROOT)}:{lineno}: {line.strip()[:110]}"
        for path in _iter_code_files()
        for lineno, line in _iter_lines(path)
        if _MACHINE_PATH.search(line)
    ]
    assert not hits, (
        "发现本机绝对路径，请改用 Path(__file__).resolve().parents[1] / $PSScriptRoot / 从 PATH 解析：\n"
        + "\n".join(hits[:10])
    )


def test_scripts_have_no_drive_letter_literals():
    """`scripts/` 更严：连普通盘符字面量都不该出现（排除 URL 协议）。"""
    hits = []
    for path in (ROOT / "scripts").rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        for lineno, line in _iter_lines(path):
            if "://" in line:
                continue
            if _DRIVE_LITERAL.search(line):
                hits.append(f"{path.relative_to(ROOT)}:{lineno}: {line.strip()[:110]}")
    assert not hits, "scripts/ 下不应出现盘符路径字面量：\n" + "\n".join(hits[:10])
