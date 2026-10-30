"""合并脚本：给源 CSV 补 source / crawl_time，且不覆盖已有非空值。"""
import pandas as pd

from scripts.merge_jobs import _with_source_meta


def test_with_source_meta_fills_missing_fields(tmp_path):
    p = tmp_path / "tencent_ai_jobs.csv"
    p.write_text("job_id,title\n1,AI\n", encoding="utf-8")
    part = _with_source_meta(pd.DataFrame({"job_id": ["1"], "title": ["AI"]}),
                             p, "tencent")
    assert part["source"].tolist() == ["tencent"]
    assert part.loc[0, "crawl_time"].endswith("+00:00")
    assert len(part.loc[0, "crawl_time"]) >= 19


def test_with_source_meta_keeps_existing_values(tmp_path):
    p = tmp_path / "tencent_ai_jobs.csv"
    p.write_text("job_id\n1\n", encoding="utf-8")
    part = _with_source_meta(
        pd.DataFrame({"job_id": ["1"], "source": ["manual"],
                      "crawl_time": ["2026-10-01T00:00:00+00:00"]}),
        p, "tencent",
    )
    assert part.loc[0, "source"] == "manual"
    assert part.loc[0, "crawl_time"] == "2026-10-01T00:00:00+00:00"
