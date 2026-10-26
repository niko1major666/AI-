"""美团招聘爬虫解析逻辑测试（全部离线，不发真实请求）。"""
import pandas as pd

import src.crawler.meituan as meituan

SCHEMA = {"job_id", "company", "title", "location", "salary", "experience",
          "education", "jd_text", "department", "publish_time"}


class FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class FakeSession:
    """够用的 requests.Session 替身：headers + post 记录请求体并返回预置 JSON。"""

    def __init__(self, payloads=None):
        self.headers = {}
        self.payloads = list(payloads or [])
        self.posts = []

    def post(self, url, json=None, timeout=None):
        self.posts.append((url, json))
        payload = self.payloads.pop(0) if self.payloads else {"status": 1, "data": {}}
        return FakeResp(payload)


def _page(items, total=None):
    return {"status": 1, "message": "成功",
            "data": {"list": items,
                     "page": {"pageNo": 1, "pageSize": meituan.PAGE_SIZE,
                              "totalPage": 0,
                              "totalCount": total if total is not None else len(items)}}}


def _item(**kw):
    base = {
        "jobUnionId": "4697320043",
        "name": "AI全栈工程师",
        "jobFamily": "技术类",
        "jobFamilyGroup": "软件",
        "cityList": [{"name": "北京市"}, {"name": "上海市"}],
        "workYear": "不限",
        "jobDuty": "岗位职责\n1、负责 AI 应用的全栈开发。",
        "jobRequirement": "岗位要求\n1、熟悉 Python 与 React。",
        "refreshTime": 1786960999000,
        "firstPostTime": None,
    }
    base.update(kw)
    return base


def test_to_rows_maps_fields():
    r = meituan.to_rows([_item()])[0]
    assert set(r) == SCHEMA
    assert r["job_id"] == "meituan_4697320043"
    assert r["company"] == "美团"
    assert r["title"] == "AI全栈工程师"
    assert r["location"] == "北京市、上海市"
    assert r["experience"] == "不限"
    assert r["department"] == "技术类"
    assert r["publish_time"] == "2026-08-17"
    assert r["jd_text"].startswith("岗位职责")
    assert "React" in r["jd_text"]
    assert r["salary"] == "" and r["education"] == ""


def test_to_rows_tolerates_missing_fields():
    r = meituan.to_rows([{"jobUnionId": "1"}])[0]
    assert r["job_id"] == "meituan_1"
    assert r["title"] == "" and r["location"] == "" and r["jd_text"] == ""
    assert r["department"] == "" and r["publish_time"] == ""
    assert r["experience"] == ""


def test_to_rows_joins_duty_and_requirement():
    r = meituan.to_rows([_item(jobDuty="做算法", jobRequirement="要会 Python")])[0]
    assert r["jd_text"] == "做算法\n要会 Python"
    # 只有一侧时不补空行，且去掉首尾空白
    assert meituan.to_rows([_item(jobRequirement="  ")])[0]["jd_text"] == \
        "岗位职责\n1、负责 AI 应用的全栈开发。"


def test_to_rows_skips_blank_city_names():
    r = meituan.to_rows([_item(cityList=[{"name": "北京市"}, {"name": " "}, {}])])[0]
    assert r["location"] == "北京市"


def test_epoch_ms_to_date_handles_bad_input():
    assert meituan._epoch_ms_to_date(None) == ""
    assert meituan._epoch_ms_to_date("") == ""
    assert meituan._epoch_ms_to_date("abc") == ""
    assert meituan._epoch_ms_to_date(1786960999000) == "2026-08-17"
    # 秒级时间戳被当成毫秒会落到 1970 年之前，属于脏数据 → 保留可解析行为即可
    assert meituan._epoch_ms_to_date(0) == ""


def test_filter_rows_keeps_tech_family_only():
    rows = [{"department": "技术类"}, {"department": "运营类"},
            {"department": "零售类"}, {"department": "产品类"}]
    assert meituan.filter_rows(rows) == [{"department": "技术类"}]


def test_filter_rows_empty_means_no_filter():
    rows = [{"department": "运营类"}, {"department": ""}]
    assert meituan.filter_rows(rows, ()) == rows


def test_keep_job_families_is_tech_only():
    assert meituan.KEEP_JOB_FAMILIES == ("技术类",)


def test_new_token_shape():
    t1 = meituan.new_token()
    assert len(t1["u_query_id"]) == 32
    assert t1["u_query_id"].isalnum()
    assert t1["r_query_id"].isdigit() and len(t1["r_query_id"]) == 21
    assert meituan.new_token()["u_query_id"] != t1["u_query_id"]


def test_fetch_page_posts_nested_page_body():
    fake = FakeSession([_page([_item()], total=3231)])
    items, total = meituan.fetch_page(fake, 2, {"u_query_id": "u", "r_query_id": "r"})
    assert len(items) == 1 and total == 3231
    url, body = fake.posts[0]
    assert url == meituan.BASE + meituan.LIST_PATH
    # 分页参数必须嵌在 page 对象里，顶层 pageNo 会被服务端忽略
    assert body == {"page": {"pageSize": meituan.PAGE_SIZE, "pageNo": 2},
                    "jobShareType": meituan.JOB_SHARE_TYPE,
                    "u_query_id": "u", "r_query_id": "r"}


def test_fetch_page_handles_empty_data():
    assert meituan.fetch_page(FakeSession([{"status": 1, "data": None}]), 1, {}) == ([], 0)


def test_fetch_page_raises_on_unexpected_status():
    fake = FakeSession([{"status": 0, "message": "请求参数格式不正确！", "data": None}])
    try:
        meituan.fetch_page(fake, 1, {})
    except RuntimeError as exc:
        assert "请求参数格式不正确" in str(exc)
    else:  # pragma: no cover - 失败分支
        raise AssertionError("status != 1 应抛 RuntimeError")


def test_crawl_all_reuses_one_token_and_dedups(monkeypatch):
    pages = {1: ([_item(), _item(jobUnionId="2")], 3),
             2: ([_item(jobUnionId="3")], 3)}
    tokens = []

    def fake_fetch(s, page, token, page_size=meituan.PAGE_SIZE):
        tokens.append(token.copy())
        return pages[min(page, 2)]

    monkeypatch.setattr(meituan, "fetch_page", fake_fetch)
    monkeypatch.setattr(meituan.time, "sleep", lambda s: None)
    rows = meituan.crawl_all(FakeSession())
    assert [r["job_id"] for r in rows] == ["meituan_4697320043", "meituan_2", "meituan_3"]
    # 整轮只用一个查询 token：换 token 会让服务端退回第 1 页
    assert len(tokens) == 2 and tokens[0] == tokens[1]


def test_crawl_all_raises_when_pagination_returns_same_page(monkeypatch):
    """每页都返回同一批（token 失效的典型症状）：必须报错而不是当成抓完了。"""
    monkeypatch.setattr(meituan, "fetch_page",
                        lambda *a, **k: ([_item(), _item(jobUnionId="2")], 4))
    monkeypatch.setattr(meituan.time, "sleep", lambda s: None)
    try:
        meituan.crawl_all(FakeSession())
    except RuntimeError as exc:
        assert "2/4" in str(exc)
    else:  # pragma: no cover - 失败分支
        raise AssertionError("唯一条数不足 total 时应抛 RuntimeError")


def test_crawl_all_stops_on_empty_page(monkeypatch):
    monkeypatch.setattr(meituan, "fetch_page", lambda *a, **k: ([], 0))
    assert meituan.crawl_all(FakeSession()) == []


def test_main_writes_filtered_csv(monkeypatch, tmp_path):
    monkeypatch.setattr(meituan, "fetch_page",
                        lambda *a, **k: ([_item(), _item(jobUnionId="2", jobFamily="运营类")], 2))
    monkeypatch.setattr(meituan.requests, "Session", FakeSession)
    out = tmp_path / "meituan.csv"
    meituan.main(["--out", str(out)])
    df = pd.read_csv(out)
    assert len(df) == 1
    assert list(df.columns) == meituan._COLS
    assert df.loc[0, "job_id"] == "meituan_4697320043"


def test_main_all_keeps_every_family(monkeypatch, tmp_path):
    monkeypatch.setattr(meituan, "fetch_page",
                        lambda *a, **k: ([_item(), _item(jobUnionId="2", jobFamily="运营类")], 2))
    monkeypatch.setattr(meituan.requests, "Session", FakeSession)
    out = tmp_path / "meituan_all.csv"
    meituan.main(["--all", "--out", str(out)])
    assert len(pd.read_csv(out)) == 2
