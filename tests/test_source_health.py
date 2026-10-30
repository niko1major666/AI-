"""来源健康报告：分组、超期、零技能率、状态与 Markdown 输出。"""
from src.data import source_health


def _jobs(source, n, last_seen, publish_time="2026-10-01"):
    return [{
        "job_id": f"{source}_{i}", "source": source, "company": "公司A",
        "last_seen_at": last_seen, "publish_time": publish_time if i == 0 else "",
    } for i in range(n)]


def test_build_report_groups_and_status():
    jobs = _jobs("tencent", 3, "2026-10-26T00:00:00+00:00")
    jobs += _jobs("old_source", 2, "2026-08-01T00:00:00+00:00", publish_time="")
    jobs += _jobs("bad_source", 20, "2026-10-26T00:00:00+00:00")
    zero = {"bad_source_0", "bad_source_1", "bad_source_2", "bad_source_3",
            "bad_source_4", "bad_source_5", "bad_source_6", "bad_source_7",
            "bad_source_8", "bad_source_9", "tencent_0"}
    state = {"jobs": {
        "gone": {"source": "old_source", "active": False},
        "alive": {"source": "tencent", "active": True},
    }}
    report = source_health.build_report(
        jobs, state=state, zero_skill_ids=zero, as_of="2026-10-26T12:00:00Z",
        stale_days=30,
    )
    by_source = {s["source"]: s for s in report["sources"]}
    assert report["totals"]["jobs"] == 25
    assert report["totals"]["sources"] == 3
    assert report["totals"]["zero_skill_jobs"] == 11
    assert report["totals"]["inactive_history_jobs"] == 1

    assert by_source["tencent"]["jobs"] == 3
    assert by_source["tencent"]["status"] == "ok"
    assert by_source["old_source"]["status"] == "warn"
    assert by_source["old_source"]["stale_jobs"] == 2
    assert by_source["old_source"]["inactive_jobs"] == 1
    assert by_source["bad_source"]["status"] == "fail"
    assert by_source["bad_source"]["zero_skill_ratio"] == 0.5
    # 岗位数降序
    assert [s["source"] for s in report["sources"]][0] == "bad_source"


def test_build_report_without_extraction_and_markdown():
    jobs = _jobs("tencent", 2, "2026-10-26T00:00:00+00:00")
    report = source_health.build_report(jobs, as_of="2026-10-27T00:00:00Z")
    assert report["totals"]["zero_skill_jobs"] is None
    assert report["sources"][0]["zero_skill_jobs"] is None
    assert report["as_of"] == "2026-10-27T00:00:00+00:00"

    md = source_health.render_markdown(report)
    assert "# 数据源健康（自动生成）" in md
    assert "腾讯" in md
    assert "50.0%" in md  # 2 条里 1 条有 publish_time
    assert "| 2 | 1 |" in md  # 岗位数 / 公司数
    assert "✅ 正常" in md
    assert "基准时间" in md
