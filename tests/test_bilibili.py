"""哔哩哔哩招聘爬虫解析逻辑测试（全部离线，不发真实请求）。"""
import src.crawler.bilibili as bili

SCHEMA = {"job_id", "company", "title", "location", "salary", "experience",
          "education", "jd_text", "department", "publish_time"}


class FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class FakeSession:
    """够用的 requests.Session 替身：headers + get/post 返回预置 JSON。"""

    def __init__(self, get_payloads=None, post_payloads=None):
        self.headers = {}
        self.get_payloads = list(get_payloads or [])
        self.post_payloads = list(post_payloads or [])
        self.gets = []
        self.posts = []

    def get(self, url, timeout=None):
        self.gets.append(url)
        payload = self.get_payloads.pop(0) if self.get_payloads else {"code": 0, "data": "tok"}
        return FakeResp(payload)

    def post(self, url, json=None, timeout=None):
        self.posts.append((url, json))
        payload = self.post_payloads.pop(0) if self.post_payloads else {"code": 0, "data": {}}
        return FakeResp(payload)


def test_to_rows_maps_social_fields():
    batch = [{
        "id": 27770,
        "positionName": "大模型算法工程师",
        "workLocation": "上海",
        "positionDescription": "工作职责:\n1、负责多模态大模型训练。\n工作要求:\n1、熟悉 PyTorch。",
        "postCodeName": "技术类",
        "pushTime": "2026-10-23 16:22:55",
        "recruitType": 0,
    }]
    rows = bili.to_rows(batch, "bili")
    assert len(rows) == 1
    r = rows[0]
    assert set(r) == SCHEMA
    assert r["job_id"] == "bili_27770"
    assert r["company"] == "哔哩哔哩"
    assert r["title"] == "大模型算法工程师"
    assert r["location"] == "上海"
    assert r["department"] == "技术类"
    assert r["publish_time"] == "2026-10-23"
    assert r["jd_text"].startswith("工作职责:")
    assert "PyTorch" in r["jd_text"]
    assert r["salary"] == "" and r["experience"] == "" and r["education"] == ""


def test_to_rows_uses_prefix_from_caller():
    rows = bili.to_rows([{"id": 31020, "positionName": "算法实习生"}], "bilic")
    assert rows[0]["job_id"] == "bilic_31020"


def test_to_rows_tolerates_missing_fields():
    r = bili.to_rows([{"id": 1}], "bili")[0]
    assert r["job_id"] == "bili_1"
    assert r["title"] == "" and r["location"] == "" and r["jd_text"] == ""
    assert r["department"] == "" and r["publish_time"] == ""


def test_sources_define_social_and_campus():
    paths = {path for path, _, _ in bili.SOURCES}
    assert paths == {"/api/srs/position/positionList", "/api/campus/position/positionList"}
    prefixes = [prefix for _, prefix, _ in bili.SOURCES]
    assert prefixes == ["bili", "bilic"]


def test_filter_rows_keeps_tech_and_ai_only():
    rows = [{"department": "技术类"}, {"department": "AI类"},
            {"department": "产品运营类"}, {"department": "内容类"}]
    kept = bili.filter_rows(rows)
    assert [r["department"] for r in kept] == ["技术类", "AI类"]


def test_filter_rows_empty_means_no_filter():
    rows = [{"department": "内容类"}, {"department": ""}]
    assert bili.filter_rows(rows, ()) == rows


def test_new_session_sets_appkey_and_csrf():
    fake = FakeSession(get_payloads=[{"code": 0, "data": "token-1"}])
    original = bili.requests.Session
    bili.requests.Session = lambda: fake
    try:
        s = bili.new_session()
    finally:
        bili.requests.Session = original
    assert s.headers["X-CSRF"] == "token-1"
    assert s.headers["X-AppKey"] == "ops.ehr-api.auth"
    assert s.headers["X-UserType"] == "2"
    assert fake.gets == [bili.BASE + bili.CSRF_PATH]


def test_new_session_raises_without_token():
    fake = FakeSession(get_payloads=[{"code": -1, "data": None}])
    original = bili.requests.Session
    bili.requests.Session = lambda: fake
    try:
        try:
            bili.new_session()
        except RuntimeError as exc:
            assert "CSRF" in str(exc)
        else:  # pragma: no cover - 失败分支
            raise AssertionError("缺 token 时应抛 RuntimeError")
    finally:
        bili.requests.Session = original


def test_post_refreshes_token_and_retries_once():
    fake = FakeSession(get_payloads=[{"code": 0, "data": "token-2"}],
                       post_payloads=[{"code": -3, "message": "csrf不能为空"},
                                      {"code": 0, "data": {"list": [{"id": 1}]}}])
    data = bili._post(fake, "/api/srs/position/positionList", {"pageNum": 1})
    assert data == {"list": [{"id": 1}]}
    assert fake.headers["X-CSRF"] == "token-2"
    assert len(fake.posts) == 2


def test_post_raises_on_unexpected_code():
    fake = FakeSession(post_payloads=[{"code": 500, "message": "系统繁忙"}])
    try:
        bili._post(fake, "/api/srs/position/positionList", {"pageNum": 1})
    except RuntimeError as exc:
        assert "系统繁忙" in str(exc)
    else:  # pragma: no cover - 失败分支
        raise AssertionError("非 0 code 应抛 RuntimeError")


def test_fetch_page_returns_list_and_pagination():
    fake = FakeSession(post_payloads=[{"code": 0, "data": {
        "list": [{"id": 1}], "pages": 5, "total": 477, "size": 100}}])
    lst, pages, total = bili.fetch_page(fake, "/api/srs/position/positionList", 1)
    assert (lst, pages, total) == ([{"id": 1}], 5, 477)
    assert fake.posts[0][1] == {"pageNum": 1, "pageSize": bili.PAGE_SIZE}


def test_fetch_page_handles_empty_data():
    fake = FakeSession(post_payloads=[{"code": 0, "data": None}])
    assert bili.fetch_page(fake, "/api/campus/position/positionList", 1) == ([], 0, 0)


def test_crawl_source_dedups_and_stops_at_last_page(monkeypatch):
    pages = {
        1: ([{"id": 1, "positionName": "算法"}, {"id": 1, "positionName": "算法"}], 2, 2),
        2: ([{"id": 2, "positionName": "后端"}], 2, 2),
    }
    monkeypatch.setattr(bili, "fetch_page", lambda s, path, page, page_size=100: pages[page])
    monkeypatch.setattr(bili.time, "sleep", lambda s: None)
    rows = bili.crawl_source(FakeSession(), "/api/srs/position/positionList", "bili", "社招")
    assert [r["job_id"] for r in rows] == ["bili_1", "bili_2"]


def test_crawl_source_stops_on_empty_page(monkeypatch):
    monkeypatch.setattr(bili, "fetch_page", lambda *a, **k: ([], 0, 0))
    assert bili.crawl_source(FakeSession(), "/api/campus/position/positionList", "bilic", "校招") == []

