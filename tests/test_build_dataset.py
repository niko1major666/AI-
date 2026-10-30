import json
from pathlib import Path

import pytest
import yaml

from src.data import build_dataset

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "raw" / "sample_jobs.csv"


def _write_config(tmp_path):
    cfg = {
        "source": {"type": "local_csv", "path": str(SAMPLE), "job_prefix": "jd"},
        "column_mapping": {
            "job_id": "job_id", "company": "company", "title": "title",
            "location": "location", "salary": "salary", "experience": "experience",
            "education": "education", "jd_text": "jd_text",
        },
        "cleaning": {"min_jd_chars": 30, "normalize_company": True},
        "output": {
            "jobs_jsonl": "data/processed/jobs.jsonl",
            "stats_path": "data/processed/build_stats.json",
        },
    }
    p = tmp_path / "dataset.yaml"
    p.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    return p


def test_build_on_sample(tmp_path):
    cfg = _write_config(tmp_path)
    out_dir = tmp_path / "out"
    stats = build_dataset.build(cfg, out_dir=out_dir)

    assert stats["raw_rows"] == 9
    assert stats["cleaned_rows"] == 9
    assert stats["dropped_short"] == 0
    assert stats["deduped_rows"] == 0
    assert stats["company_count"] == 8
    assert "华为技术" in stats["companies"]

    jobs = out_dir / "jobs.jsonl"
    lines = [json.loads(x) for x in jobs.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 9

    by_id = {r["job_id"]: r for r in lines}
    assert by_id["hw_001"]["salary_min_k"] == 30.0
    assert by_id["hw_001"]["salary_months"] == 15
    assert by_id["bytedance_001"]["salary_months"] is None
    assert by_id["kuangshi_001"]["salary_min_k"] is None  # 面议
    assert by_id["sensetime_001"]["salary_min_k"] == pytest.approx(25.0, abs=0.1)

    # 新鲜度字段向后兼容：样例没有 source/crawl_time → 用构建类型/构建时间兜底
    for r in lines:
        assert r["source"] == "local_csv"
        assert r["is_active"] is True
        assert r["first_seen_at"] and r["last_seen_at"]
        assert r["first_seen_at"] == r["last_seen_at"]
    state = json.loads((out_dir / "job_freshness.json").read_text(encoding="utf-8"))
    assert len(state["jobs"]) == 9
    assert all(x["active"] for x in state["jobs"].values())

    # 再构建一次：first_seen 不应被改写
    first_seen = by_id["hw_001"]["first_seen_at"]
    build_dataset.build(cfg, out_dir=out_dir)
    lines2 = [json.loads(x) for x in jobs.read_text(encoding="utf-8").splitlines()]
    assert {r["job_id"]: r for r in lines2}["hw_001"]["first_seen_at"] == first_seen


def test_build_keeps_source_and_crawl_time(tmp_path):
    raw = tmp_path / "one.csv"
    raw.write_text(
        "job_id,company,title,jd_text,source,crawl_time\n"
        "x1,测试公司,AI 工程师,负责大模型训练与推理，熟悉 Python 和 PyTorch,tencent,"
        "2026-10-01T00:00:00+00:00\n",
        encoding="utf-8",
    )
    cfg = {
        "source": {"type": "local_csv", "path": str(raw), "job_prefix": "jd"},
        "column_mapping": {},
        "cleaning": {"min_jd_chars": 10, "normalize_company": True},
        "output": {"jobs_jsonl": "unused.jsonl"},
    }
    cfg_path = tmp_path / "dataset.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    out_dir = tmp_path / "out"
    build_dataset.build(cfg_path, out_dir=out_dir)
    row = json.loads((out_dir / "jobs.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert row["source"] == "tencent"
    assert row["crawl_time"] == "2026-10-01T00:00:00+00:00"
    assert row["last_seen_at"] == "2026-10-01T00:00:00+00:00"
