"""简历隐私保护：上传边界、PII 脱敏与会话内 LLM 配额。

设计目标
--------
- **最小化外发**：只有用户显式开启 AI 增强时，才把简历文本发送给 DeepSeek；
  发送前强制替换邮箱、手机号、证件号、银行卡号、微信/QQ 与详细住址。
- **最小化驻留**：应用不把简历写入磁盘/数据库；页面缓存改为 Streamlit session
  级，不使用跨会话的 `st.cache_data`。
- **可解释**：脱敏按类别计数，页面向用户展示本次隐藏了多少处直接联系方式。

注意：姓名、学校、公司、项目经历等正文仍可能间接识别个人。隐私说明必须如实告知，
不能宣称“完全匿名”。需要绝对不上传时，用户应关闭 AI 增强。
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

PRIVACY_NOTICE_VERSION = "2026-10-30"

MAX_UPLOAD_BYTES = 5 * 1024 * 1024          # 单个文件 5 MB
MAX_RESUME_CHARS = 50_000                   # 解析后文本上限
MAX_PDF_PAGES = 30                          # PDF 页数上限
MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024  # DOCX 解压后上限（防 zip bomb）
MAX_RESUME_LLM_CALLS = 10                   # 每个会话最多 10 次简历 LLM 解析
LLM_RESUME_CHARS = 6_000                    # 单次外发给 LLM 的简历文本上限

SUPPORTED_SUFFIXES = (".pdf", ".docx", ".txt", ".md", ".text")

# 顺序很重要：先处理证件号/邮箱，再处理可能包含数字子串的银行卡与手机号。
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_ID_RE = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_BANK_RE = re.compile(r"(?<!\d)\d{16,19}(?!\d)")
_LABELED_BANK_RE = re.compile(
    r"((?:银行卡号|卡号|银行账号|收款账号)\s*[:：]?\s*)(?:\d[ -]?){16,19}(?!\d)"
)
_LABELED_SOCIAL_RE = re.compile(
    r"((?:微信号?|WeChat|微信|QQ号?|WhatsApp)\s*[:：]?\s*)([A-Za-z0-9_+.-]{5,24})",
    re.IGNORECASE,
)
_LABELED_ADDRESS_RE = re.compile(
    r"((?:住址|地址|现居地?|居住地|通讯地址)\s*[:：]\s*)[^\n\r]{2,60}"
)

_SIMPLE_PATTERNS = (
    ("邮箱", _EMAIL_RE, "[邮箱已隐藏]"),
    ("手机号", _PHONE_RE, "[手机号已隐藏]"),
    ("身份证号", _ID_RE, "[身份证号已隐藏]"),
    ("银行卡号", _BANK_RE, "[银行卡号已隐藏]"),
)


class UploadValidationError(ValueError):
    """上传文件或解析文本不满足安全边界。"""


@dataclass
class MaskedText:
    """脱敏结果：`text` 可安全外发，`counts` 便于向用户解释。"""

    text: str
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    @property
    def summary(self) -> str:
        if not self.counts:
            return "未检测到直接联系方式"
        return "、".join(f"{name} {count} 处" for name, count in self.counts.items())


def _bump(counts: dict[str, int], name: str, amount: int = 1) -> None:
    counts[name] = counts.get(name, 0) + amount


def mask_pii(text: str) -> MaskedText:
    """替换简历中的高敏感联系方式；对普通技能/经历文本保持原样。

    只做确定性正则替换，不调用任何外部服务。姓名、学校、公司等正文不做替换，
    因为它们是简历匹配所需信息，且简单正则无法可靠识别/恢复。
    """
    masked = str(text or "")
    counts: dict[str, int] = {}

    for name, pattern, replacement in _SIMPLE_PATTERNS:
        def _replace(_match, _name=name, _replacement=replacement) -> str:
            _bump(counts, _name)
            return _replacement

        masked = pattern.sub(_replace, masked)

    def _replace_labeled(match: re.Match, name: str, label: str) -> str:
        # 银行卡号可能被身份证规则先命中一部分；只有确实发生了替换才计数
        _bump(counts, name)
        return f"{match.group(1)}{label}"

    masked = _LABELED_BANK_RE.sub(
        lambda m: _replace_labeled(m, "银行卡号", "[银行卡号已隐藏]"), masked)
    masked = _LABELED_SOCIAL_RE.sub(
        lambda m: _replace_labeled(m, "社交账号", "[社交账号已隐藏]"), masked)
    masked = _LABELED_ADDRESS_RE.sub(
        lambda m: _replace_labeled(m, "详细住址", "[详细住址已隐藏]"), masked)

    return MaskedText(text=masked, counts=counts)


def validate_upload(filename: str, data: bytes) -> None:
    """校验文件类型、大小与基础文件头；不通过时抛出可展示给用户的错误。"""
    suffix = Path(str(filename or "")).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        supported = " / ".join(s.lstrip(".").upper() for s in SUPPORTED_SUFFIXES)
        raise UploadValidationError(f"不支持的文件类型：{suffix or '未知'}（支持 {supported}）")
    if not data:
        raise UploadValidationError("文件为空，请重新选择")
    if len(data) > MAX_UPLOAD_BYTES:
        size_mb = len(data) / 1024 / 1024
        raise UploadValidationError(
            f"文件过大：{size_mb:.1f} MB（上限 {MAX_UPLOAD_BYTES // 1024 // 1024} MB）"
        )
    if suffix == ".pdf" and not data.lstrip().lower().startswith(b"%pdf-"):
        raise UploadValidationError("文件扩展名为 PDF，但内容不是有效的 PDF")
    if suffix == ".docx":
        if not data.startswith(b"PK\x03\x04"):
            raise UploadValidationError("文件扩展名为 DOCX，但内容不是有效的 DOCX")
        try:
            with zipfile.ZipFile(BytesIO(data)) as archive:
                unpacked = sum(item.file_size for item in archive.infolist())
        except (zipfile.BadZipFile, OSError) as exc:
            raise UploadValidationError("DOCX 文件损坏或无法读取") from exc
        if unpacked > MAX_DOCX_UNCOMPRESSED_BYTES:
            raise UploadValidationError(
                f"DOCX 解压后过大：{unpacked / 1024 / 1024:.1f} MB"
                f"（上限 {MAX_DOCX_UNCOMPRESSED_BYTES // 1024 // 1024} MB）"
            )


def validate_resume_text(text: str) -> str:
    """校验解析出的文本非空且不超过上限，返回去除首尾空白后的文本。"""
    clean = str(text or "").strip()
    if not clean:
        raise UploadValidationError(
            "未能从文件中提取到文字。扫描件请确认已安装 OCR 依赖，或改用可复制文字的 PDF/DOCX/TXT"
        )
    if len(clean) > MAX_RESUME_CHARS:
        raise UploadValidationError(
            f"解析文本过长：{len(clean):,} 字（上限 {MAX_RESUME_CHARS:,} 字），请精简后重试"
        )
    return clean


def privacy_notice_markdown() -> str:
    """页面内展示的简明隐私说明（完整版见 docs/privacy.md）。"""
    size_mb = MAX_UPLOAD_BYTES // 1024 // 1024
    return f"""
**简历在本应用中的处理方式**

- 文件在当前 Streamlit 会话的请求内存中解析，应用**不会把简历写入岗位数据库或项目目录**；托管平台仍可能保留运维访问日志或临时缓存，具体受其隐私政策约束。
- **不开启 AI 增强**：解析只在本服务进程内用正则完成，不调用任何第三方 API。
- **开启 AI 增强**：仅发送简历**前 {LLM_RESUME_CHARS:,} 字**给 DeepSeek API；发送前自动隐藏邮箱、手机号、身份证号、银行卡号、微信/QQ 与详细住址。姓名、学校、公司、项目经历等正文仍可能包含可识别信息，**并非完全匿名**。
- 结构化解析结果只保存在当前会话；刷新或关闭页面即清空。每会话最多进行 {MAX_RESUME_LLM_CALLS} 次 AI 简历解析。
- 上传限制：单个文件 ≤ {size_mb} MB；PDF ≤ {MAX_PDF_PAGES} 页；解析文本 ≤ {MAX_RESUME_CHARS:,} 字；支持 PDF / DOCX / TXT / MD。
- 请只上传**你自己的**简历；不要上传他人、未成年人或你不具备处理授权的个人信息。不同意时可关闭 AI 增强或直接不上传。

完整说明：`docs/privacy.md`（版本 {PRIVACY_NOTICE_VERSION}）
"""
