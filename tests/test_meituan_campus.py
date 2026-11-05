"""美团校招/实习爬虫的解析回归（不发网络请求）。

接口字段名容易踩坑：没有 `jobId`（用 `jobUnionId`）、发布时间在 `refreshTime`（毫秒串）、
城市在 `cityList`。这里用固定 payload 锁住映射，避免下次改接口时静默产出空列。
"""

import re

from src.crawler.meituan_campus import _city, _job_id, to_rows

ITEM = {
    "jobUnionId": "abc123",
    "name": "后端开发工程师（校招）",
    "jobFamily": "技术类",
    "jobDuty": "岗位职责\n1. 负责服务端开发",
    "jobRequirement": "岗位要求\n1. 熟悉 Python / Go",
    "cityList": [{"name": "北京"}, {"name": "上海"}],
    "workYear": "应届",
    "department": "到店事业群",
    "refreshTime": "1786960999000",
}

NON_TECH = dict(ITEM, jobUnionId="xyz789", jobFamily="运营类", name="内容运营")


def test_maps_core_fields():
    row = to_rows([ITEM])[0]
    assert row["job_id"] == "mtc_abc123"
    assert row["company"] == "美团"
    assert row["title"] == "后端开发工程师（校招）"
    assert row["location"] == "北京、上海"
    assert row["department"] == "到店事业群"


def test_jd_merges_duty_and_requirement():
    row = to_rows([ITEM])[0]
    assert "负责服务端开发" in row["jd_text"]
    assert "熟悉 Python" in row["jd_text"]


def test_publish_time_from_refresh_time_ms():
    row = to_rows([ITEM])[0]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["publish_time"]), row["publish_time"]


def test_non_tech_filtered_by_default_but_kept_with_all():
    assert to_rows([NON_TECH]) == []
    assert len(to_rows([NON_TECH], keep_all=True)) == 1


def test_empty_family_falls_back_to_tech_title():
    # 接口对部分岗位不给 jobFamily：技术标题要保留，非技术标题要丢
    tech = {k: v for k, v in ITEM.items() if k != "jobFamily"}
    tech["name"] = "算法工程师"
    ops = {k: v for k, v in ITEM.items() if k != "jobFamily"}
    ops["name"] = "校园招聘运营"
    assert len(to_rows([tech])) == 1
    assert to_rows([ops]) == []


def test_missing_id_falls_back_to_hash():
    item = {k: v for k, v in ITEM.items() if k != "jobUnionId"}
    job_id = _job_id(item)
    assert job_id.startswith("mtc_h") and len(job_id) > 8


def test_city_falls_back_to_plain_field():
    assert _city({"city": "深圳"}) == "深圳"
    assert _city({}) == ""
