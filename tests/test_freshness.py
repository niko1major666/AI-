"""岗位新鲜度纯函数：时间解析、状态增量、越界降级。"""
import json

from src.data import freshness


def test_parse_and_age_days():
    assert freshness.parse_time("2026-10-26T11:23:46+00:00").year == 2026
    assert freshness.parse_time("2026-10-26T11:23:46Z").tzinfo is not None
    assert freshness.parse_time("2026-10-26").hour == 0
    assert freshness.parse_time("不是时间") is None

    assert freshness.age_days("2026-10-26T00:00:00Z",
                              now="2026-10-30T00:00:00Z") == 4
    assert freshness.age_days("2026-10-30T12:00:00Z",
                              now="2026-10-30T00:00:00Z") == 0  # 未来不出现负数
    assert freshness.age_days("bad", now="2026-10-30T00:00:00Z") is None


def test_freshness_label_and_stale():
    now = "2026-10-30T12:00:00Z"
    assert freshness.freshness_label("2026-10-30T08:00:00Z", now=now) == "今天更新"
    assert freshness.freshness_label("2026-10-29T08:00:00Z", now=now) == "昨天更新"
    assert freshness.freshness_label("2026-10-26T08:00:00Z", now=now) == "4 天前更新"
    assert freshness.freshness_label("", now=now) == ""

    assert freshness.is_stale("2026-09-01T00:00:00Z", now=now)
    assert not freshness.is_stale("2026-10-01T00:00:00Z", now=now)
    assert not freshness.is_stale("", now=now)  # 缺时间不误报


def test_filter_by_age_keeps_unknown_and_recent():
    now = "2026-10-30T12:00:00Z"
    rows = [
        {"job_id": "old", "last_seen_at": "2026-09-01T00:00:00Z"},
        {"job_id": "new", "last_seen_at": "2026-10-26T00:00:00Z"},
        {"job_id": "unknown"},
    ]
    assert [r["job_id"] for r in freshness.filter_by_age(rows, 30, now=now)] == ["new", "unknown"]
    assert [r["job_id"] for r in freshness.filter_by_age(
        rows, 30, now=now, keep_unknown=False)] == ["new"]
    assert freshness.filter_by_age(rows, None, now=now) == rows


def test_annotate_jobs_preserves_first_seen_and_marks_inactive():
    first_run = [{
        "job_id": "a", "source": "tencent", "crawl_time": "2026-10-01T00:00:00Z",
    }, {
        "job_id": "b", "source": "tencent", "crawl_time": "2026-10-01T00:00:00Z",
    }]
    rows1, state1 = freshness.annotate_jobs(first_run, observed_at="2026-10-02T00:00:00Z")
    assert [r["is_active"] for r in rows1] == [True, True]
    assert {r["first_seen_at"] for r in rows1} == {"2026-10-01T00:00:00+00:00"}
    assert {r["last_seen_at"] for r in rows1} == {"2026-10-01T00:00:00+00:00"}
    assert state1["jobs"]["a"]["active"] is True

    # 第二轮只有 a：a 的 last_seen 前移，b 被标为 inactive，first_seen 不变
    rows2, state2 = freshness.annotate_jobs([{
        "job_id": "a", "source": "tencent", "crawl_time": "2026-10-20T00:00:00Z",
    }], state=state1, observed_at="2026-10-21T00:00:00Z")
    assert rows2[0]["first_seen_at"] == "2026-10-01T00:00:00+00:00"
    assert rows2[0]["last_seen_at"] == "2026-10-20T00:00:00+00:00"
    assert state2["jobs"]["a"]["active"] is True
    assert state2["jobs"]["b"]["active"] is False

    # 重新出现 b：first_seen 保留，last_seen 取新值，重新 active
    rows3, state3 = freshness.annotate_jobs([{
        "job_id": "b", "source": "tencent", "crawl_time": "2026-10-25T00:00:00Z",
    }], state=state2, observed_at="2026-10-26T00:00:00Z")
    assert rows3[0]["first_seen_at"] == "2026-10-01T00:00:00+00:00"
    assert rows3[0]["last_seen_at"] == "2026-10-25T00:00:00+00:00"
    assert state3["jobs"]["b"]["active"] is True


def test_annotate_jobs_prefers_later_timestamp_and_falls_back_to_build_time():
    state = {"version": 1, "updated_at": "", "jobs": {
        "a": {"first_seen_at": "2026-10-01T00:00:00+00:00",
              "last_seen_at": "2026-10-20T00:00:00+00:00",
              "source": "tencent", "active": True},
    }}
    rows, _ = freshness.annotate_jobs([{
        "job_id": "a", "source": "tencent", "crawl_time": "2026-10-10T00:00:00Z",
    }], state=state, observed_at="2026-10-21T00:00:00Z")
    assert rows[0]["last_seen_at"] == "2026-10-20T00:00:00+00:00"  # 不倒退

    rows2, _ = freshness.annotate_jobs([{"job_id": "c", "source": "kimi"}],
                                       observed_at="2026-10-21T00:00:00Z")
    assert rows2[0]["last_seen_at"] == "2026-10-21T00:00:00+00:00"
    assert rows2[0]["first_seen_at"] == "2026-10-21T00:00:00+00:00"


def test_state_io_roundtrip_and_bad_file(tmp_path):
    p = tmp_path / "freshness.json"
    freshness.save_state(p, {"version": 1, "updated_at": "x", "jobs": {"b": {}, "a": {}}})
    loaded = freshness.load_state(p)
    assert list(loaded["jobs"]) == ["a", "b"]  # sort_keys 保证稳定 diff
    assert json.loads(p.read_text(encoding="utf-8"))["version"] == 1

    p.write_text("{bad json", encoding="utf-8")
    assert freshness.load_state(p)["jobs"] == {}
    p.write_text('{"version": "bad", "jobs": {}}', encoding="utf-8")
    assert freshness.load_state(p)["version"] == freshness.STATE_VERSION
    assert freshness.load_state(tmp_path / "missing.json")["jobs"] == {}
