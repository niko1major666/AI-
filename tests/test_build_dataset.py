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
