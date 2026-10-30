"""简历隐私边界：PII 脱敏、上传校验与用户可见说明。"""
from pathlib import Path

import pytest

from src.data.privacy import (
    LLM_RESUME_CHARS,
    MAX_RESUME_CHARS,
    MAX_UPLOAD_BYTES,
    UploadValidationError,
    mask_pii,
    privacy_notice_markdown,
    validate_resume_text,
    validate_upload,
)


def test_mask_pii_removes_direct_contact_identifiers():
    text = (
        "姓名：张三 手机 13800138000 邮箱 zhangsan@example.com "
        "身份证 110101199003071234 银行卡 6222020200001234567\n"
        "微信：zhangsan_88 地址：北京市海淀区中关村大街 1 号\n"
        "技能：Python / PyTorch"
    )
    masked = mask_pii(text)
    assert "13800138000" not in masked.text
    assert "zhangsan@example.com" not in masked.text
    assert "110101199003071234" not in masked.text
    assert "6222020200001234567" not in masked.text
    assert "zhangsan_88" not in masked.text
    assert "中关村大街" not in masked.text
    assert "Python / PyTorch" in masked.text
    assert masked.total == 6
    assert {"手机号", "邮箱", "身份证号", "银行卡号", "社交账号", "详细住址"} <= set(masked.counts)


def test_mask_pii_keeps_experience_and_metrics():
    text = "2023.06-至今 腾讯 算法工程师，准确率提升 15%，负责 5 人团队"
    masked = mask_pii(text)
    assert masked.text == text
    assert masked.total == 0
    assert masked.summary == "未检测到直接联系方式"


def test_mask_pii_does_not_treat_years_as_phone_or_bank():
    text = "2019-2023 年在校，2023 年毕业，GPA 3.8/4.0"
    assert mask_pii(text).text == text


def test_validate_upload_rejects_unsupported_empty_and_oversize():
    with pytest.raises(UploadValidationError, match="不支持的文件类型"):
        validate_upload("resume.exe", b"data")
    with pytest.raises(UploadValidationError, match="文件为空"):
        validate_upload("resume.txt", b"")
    with pytest.raises(UploadValidationError, match="文件过大"):
        validate_upload("resume.txt", b"x" * (MAX_UPLOAD_BYTES + 1))


def test_validate_upload_checks_file_signature():
    with pytest.raises(UploadValidationError, match="不是有效的 PDF"):
        validate_upload("resume.pdf", b"not a pdf")
    with pytest.raises(UploadValidationError, match="不是有效的 DOCX"):
        validate_upload("resume.docx", b"PK-not-a-real-docx")
    validate_upload("resume.txt", "熟悉 Python".encode("utf-8"))
    validate_upload("resume.pdf", b"%PDF-1.4\n%%EOF")


def test_validate_resume_text_limits_and_trims():
    assert validate_resume_text("  熟悉 Python  ") == "熟悉 Python"
    with pytest.raises(UploadValidationError, match="未能从文件中提取到文字"):
        validate_resume_text("   ")
    with pytest.raises(UploadValidationError, match="解析文本过长"):
        validate_resume_text("x" * (MAX_RESUME_CHARS + 1))


def test_privacy_notice_discloses_limits_and_non_anonymity():
    notice = privacy_notice_markdown()
    assert f"{LLM_RESUME_CHARS:,}" in notice
    assert "5 MB" in notice
    assert "并非完全匿名" in notice
    assert "docs/privacy.md" in notice


def test_privacy_doc_exists():
    # 页面只展示摘要，完整说明随仓库分发；避免摘要里的链接成为死链
    doc = Path(__file__).resolve().parents[1] / "docs" / "privacy.md"
    assert doc.exists(), "缺少 docs/privacy.md"
