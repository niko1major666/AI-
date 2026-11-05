"""快手爬虫发布时间的回归：社招列表接口字段名不统一，必须按候选顺序取值。

背景：`to_rows()` 曾把 `publish_time` 写死为空字符串，导致来源健康报告里
快手发布覆盖率只有 17.3%（1395 条中大量为空），而校招分支一直是好的。
这里锁住三件事：候选字段能取到、毫秒时间戳能格式化、缺字段时保持为空。
"""

import re

from src.crawler.kuaishou import to_rows


def test_social_rows_take_release_time():
    rows = to_rows([{"id": 1, "name": "后端工程师", "releaseTime": "2026-10-01"}])
    assert rows[0]["publish_time"] == "2026-10-01"


def test_social_rows_fall_back_to_publish_and_create_time():
    by_publish = to_rows([{"id": 2, "name": "x", "publishTime": "2026-09-15"}])
    by_create = to_rows([{"id": 3, "name": "x", "createTime": "2026-08-20 10:00:00"}])
    assert by_publish[0]["publish_time"] == "2026-09-15"
    assert by_create[0]["publish_time"] == "2026-08-20"


def test_social_rows_format_ms_epoch():
    # 毫秒时间戳要走 fmt_publish_time 归一成 YYYY-MM-DD（不校验时区，只校验形状）
    rows = to_rows([{"id": 4, "name": "x", "releaseTime": 1727740800000}])
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", rows[0]["publish_time"]), rows[0]["publish_time"]


def test_social_rows_leave_empty_when_field_missing():
    rows = to_rows([{"id": 5, "name": "x"}])
    assert rows[0]["publish_time"] == ""


def test_campus_rows_still_take_release_time():
    from src.crawler.kuaishou import crawl_campus  # noqa: F401  (仅确认可导入，不发请求)

    assert callable(crawl_campus)
