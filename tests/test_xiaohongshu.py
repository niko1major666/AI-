"""小红书招聘爬虫解析逻辑测试（全部离线，不发真实请求）。"""
import src.crawler.xiaohongshu as xhs

SCHEMA = {"job_id", "company", "title", "location", "salary", "experience",
          "education", "jd_text", "department", "publish_time"}


def test_to_rows_maps_social_fields():
    batch = [{
        "positionId": 20405,
        "positionName": "「商业产品」内容消费行业产品经理",
        "workplace": "北京市，上海市",
        "publishTime": "2026-10-20",
        "duty": "1. 负责广告分发与投放优化。",
        "qualification": "1. 2-4 年商业化产品经验。",
        "jobType": "产品经理",
    }]
    rows = xhs.to_rows(batch)
    assert len(rows) == 1
    r = rows[0]
    assert set(r) == SCHEMA
    assert r["job_id"] == "xhs_20405"
    assert r["company"] == "小红书"
    assert r["title"] == "「商业产品」内容消费行业产品经理"
    assert r["location"] == "北京市，上海市"
    assert r["department"] == "产品经理"
    assert r["publish_time"] == "2026-10-20"
    assert r["jd_text"] == "1. 负责广告分发与投放优化。\n1. 2-4 年商业化产品经验。"


def test_to_rows_campus_uses_distinct_prefix():
    rows = xhs.to_rows([{"positionId": 1, "positionName": "中央GA实习生"}], "campus")
    assert rows[0]["job_id"] == "xhsc_1"
    assert rows[0]["company"] == "小红书"


def test_to_rows_tolerates_missing_fields():
    r = xhs.to_rows([{"positionId": 7}])[0]
    assert r["job_id"] == "xhs_7"
    assert r["title"] == "" and r["location"] == "" and r["jd_text"] == ""
    assert r["department"] == "" and r["publish_time"] == ""


def test_to_rows_skips_empty_jd_join():
    r = xhs.to_rows([{"positionId": 9, "duty": "只写职责"}])[0]
    assert r["jd_text"] == "只写职责"


def test_fetch_page_builds_request(monkeypatch):
    captured = {}

    class FakeResp:
        def json(self):
            return {"statusCode": 200,
                    "data": {"list": [{"positionId": 1}], "total": 1, "totalPage": 1}}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured.update(url=url, json=json, headers=headers, timeout=timeout)
        return FakeResp()

    monkeypatch.setattr(xhs.requests, "post", fake_post)
    lst, total, total_page = xhs.fetch_page("campus", 2, page_size=50)
    assert (len(lst), total, total_page) == (1, 1, 1)
    assert captured["url"] == xhs.API
    assert captured["json"] == {"positionName": "", "pageNum": 2,
                                "pageSize": 50, "recruitType": "campus"}
    assert captured["headers"]["Referer"] == "https://job.xiaohongshu.com/campus/position"
    assert captured["timeout"] == 30


def test_fetch_page_handles_empty_data(monkeypatch):
    class FakeResp:
        def json(self):
            return {"statusCode": 500, "alertMsg": "系统繁忙"}

    monkeypatch.setattr(xhs.requests, "post", lambda *a, **k: FakeResp())
    assert xhs.fetch_page("social", 1) == ([], 0, 0)


def test_crawl_type_dedups_and_stops_at_total(monkeypatch):
    pages = {
        1: ([{"positionId": 1}, {"positionId": 1}], 3, 2),
        2: ([{"positionId": 2}, {"positionId": 3}], 3, 2),
    }
    monkeypatch.setattr(xhs, "fetch_page", lambda t, p, page_size=100: pages[p])
    monkeypatch.setattr(xhs.time, "sleep", lambda s: None)
    rows = xhs.crawl_type("social")
    assert [r["job_id"] for r in rows] == ["xhs_1", "xhs_2", "xhs_3"]


def test_crawl_type_stops_on_empty_page(monkeypatch):
    monkeypatch.setattr(xhs, "fetch_page", lambda t, p, page_size=100: ([], 0, 0))
    assert xhs.crawl_type("campus") == []


def test_crawl_type_respects_total_page_without_total(monkeypatch):
    pages = {1: ([{"positionId": 1}], 0, 1)}
    monkeypatch.setattr(xhs, "fetch_page", lambda t, p, page_size=100: pages[p])
    monkeypatch.setattr(xhs.time, "sleep", lambda s: None)
    rows = xhs.crawl_type("social")
    assert len(rows) == 1


def test_ai_keywords_cover_llm_terms():
    for kw in ("大模型", "LLM", "NLP", "Agent", "多模态"):
        assert kw in xhs.AI_KEYWORDS
