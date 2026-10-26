"""滴滴招聘爬虫解析逻辑测试（全部离线，不发真实请求）。"""
import pandas as pd

import src.crawler.didi as didi

SCHEMA = {"job_id", "company", "title", "location", "salary", "experience",
          "education", "jd_text", "department", "publish_time"}


class FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class FakeSession:
    """够用的 requests.Session 替身：headers + get 返回预置 JSON。"""

    def __init__(self, payloads=None):
        self.headers = {}
        self.payloads = list(payloads or [])
        self.gets = []

    def get(self, url, params=None, timeout=None):
        self.gets.append((url, params))
        payload = self.payloads.pop(0) if self.payloads else {"meta": {"code": 0}, "data": {}}
        return FakeResp(payload)


def _page(items, total=None):
    return {"meta": {"code": 0, "message": ""},
            "data": {"items": items, "total": total if total is not None else len(items),
                     "page": 1, "size": didi.PAGE_SIZE}}


def _item(**kw):
    base = {
        "jdId": 65957,
        "jdNo": "JR2026082500D",
        "jobName": "交易算法工程师",
        "workArea": "北京市",
        "deptName": "花小猪打车",
        "jobType": 1,
        "jobTypeName": "技术",
        "jobDuty": "岗位职责：\n1、负责交易链路算法迭代。",
        "jobQualification": "任职要求：\n1、熟悉 Python 与 Spark。",
        "createTime": "2026-08-26 14:48:27",
        "refreshTime": "2026-10-26",
    }
    base.update(kw)
    return base


def test_to_rows_maps_fields():
    rows = didi.to_rows([_item()])
    assert len(rows) == 1
    r = rows[0]
    assert set(r) == SCHEMA
    assert r["job_id"] == "didi_JR2026082500D"
    assert r["company"] == "滴滴"
    assert r["title"] == "交易算法工程师"
    assert r["location"] == "北京市"
    assert r["department"] == "技术"
    assert r["publish_time"] == "2026-10-26"
    assert r["jd_text"].startswith("岗位职责：")
    assert "Spark" in r["jd_text"]
    assert r["salary"] == "" and r["experience"] == "" and r["education"] == ""


def test_to_rows_falls_back_to_create_time():
    r = didi.to_rows([_item(refreshTime=None)])[0]
    assert r["publish_time"] == "2026-08-26"


def test_to_rows_tolerates_missing_fields():
    r = didi.to_rows([{"jdNo": "JR1"}])[0]
    assert r["job_id"] == "didi_JR1"
    assert r["title"] == "" and r["location"] == "" and r["jd_text"] == ""
    assert r["department"] == "" and r["publish_time"] == ""


def test_to_rows_joins_duty_and_qualification():
    r = didi.to_rows([_item(jobDuty="做算法", jobQualification="要会 Python")])[0]
    assert r["jd_text"] == "做算法\n要会 Python"
    # 只缺一侧时不留空行
    assert didi.to_rows([_item(jobQualification="")])[0]["jd_text"] == "岗位职责：\n1、负责交易链路算法迭代。"


def test_filter_rows_keeps_tech_only():
    rows = [{"department": "技术"}, {"department": "运营"},
            {"department": "安全"}, {"department": "产品"}]
    assert didi.filter_rows(rows) == [{"department": "技术"}]


def test_filter_rows_empty_means_no_filter():
    rows = [{"department": "运营"}, {"department": ""}]
    assert didi.filter_rows(rows, ()) == rows


def test_fetch_page_returns_items_and_total():
    fake = FakeSession([_page([_item()], total=1081)])
    items, total = didi.fetch_page(fake, 1)
    assert len(items) == 1 and total == 1081
    url, params = fake.gets[0]
    assert url == didi.BASE + didi.LIST_PATH
    assert params == {"page": 1, "size": didi.PAGE_SIZE}


def test_fetch_page_handles_empty_data():
    assert didi.fetch_page(FakeSession([{"meta": {"code": 0}, "data": None}]), 1) == ([], 0)


def test_fetch_page_raises_on_unexpected_code():
    fake = FakeSession([{"meta": {"code": 100, "message": "地址错误"}, "data": None}])
    try:
        didi.fetch_page(fake, 1)
    except RuntimeError as exc:
        assert "地址错误" in str(exc)
    else:  # pragma: no cover - 失败分支
        raise AssertionError("非 0 code 应抛 RuntimeError")


def test_crawl_all_dedups_and_stops_at_total(monkeypatch):
    pages = {
        1: ([_item(), _item()], 2),
        2: ([_item(jdNo="JR2")], 2),
    }
    monkeypatch.setattr(didi, "fetch_page", lambda s, page, page_size=100: pages[page])
    monkeypatch.setattr(didi.time, "sleep", lambda s: None)
    rows = didi.crawl_all(FakeSession())
    assert [r["job_id"] for r in rows] == ["didi_JR2026082500D", "didi_JR2"]


def test_crawl_all_stops_on_empty_page(monkeypatch):
    monkeypatch.setattr(didi, "fetch_page", lambda *a, **k: ([], 0))
    assert didi.crawl_all(FakeSession()) == []


def test_crawl_all_raises_when_page_truncated(monkeypatch):
    """服务端静默截断（空页但 total 未取全）必须报错，而不是当成抓完了。"""
    monkeypatch.setattr(didi, "fetch_page", lambda *a, **k: ([], 1081))
    try:
        didi.crawl_all(FakeSession())
    except RuntimeError as exc:
        assert "1081" in str(exc)
    else:  # pragma: no cover - 失败分支
        raise AssertionError("分页静默失效时应抛 RuntimeError")


def test_main_writes_filtered_csv(monkeypatch, tmp_path):
    monkeypatch.setattr(didi, "fetch_page",
                        lambda *a, **k: ([_item(), _item(jdNo="JR2", jobTypeName="运营")], 2))
    monkeypatch.setattr(didi.requests, "Session", FakeSession)
    out = tmp_path / "didi.csv"
    didi.main(["--out", str(out)])
    df = pd.read_csv(out)
    assert len(df) == 1
    assert list(df.columns) == didi._COLS
    assert df.loc[0, "job_id"] == "didi_JR2026082500D"


def test_keep_job_types_is_tech_only():
    assert didi.KEEP_JOB_TYPES == ("技术",)
