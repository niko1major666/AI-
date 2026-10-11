from src.data import schema


def test_jobposting_roundtrip():
    j = schema.JobPosting(
        job_id="hw_001", source="local_csv", company="华为", company_norm="华为",
        title="AI算法工程师", location="深圳", salary_raw="30-60K·15薪",
        salary_min_k=30.0, salary_max_k=60.0, salary_months=15,
        experience="3-5年", education="硕士", jd_text="原文", jd_clean="原文",
        crawl_time="2026-01-01T00:00:00+00:00", text_hash="abc123",
    )
    d = j.to_dict()
    assert d["job_id"] == "hw_001"
    assert d["salary_months"] == 15
    assert d["company_norm"] == "华为"


def test_skillspan_defaults():
    s = schema.SkillSpan(
        job_id="hw_001", skill_text="PyTorch", skill_text_norm="pytorch",
        skill_id="FRAMEWORK.PYTORCH", category="深度学习框架",
        start=0, end=7, score=0.97, method="siamese_uie",
    )
    assert s.is_must is False
    assert s.to_dict()["skill_id"] == "FRAMEWORK.PYTORCH"
