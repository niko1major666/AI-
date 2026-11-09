"""华为新站爬虫的解析回归（不发网络请求）。

老门户接口只有 2 条，v1.9.0 改用新站 `getJobPage`。这里锁住字段映射与几个坑：
- 接口用字面字符串 "None" 表示空值
- `jobDesc` 常为 None，真 JD 在 `mainBusiness` + `jobRequire`
- 城市在 `workPlace`（`cityName` 常为 "None"）
- 默认只入技术族
"""

from src.crawler.huawei import TECH_FAMILIES, _clean, to_rows

ITEM = {
    "jobId": "114740",
    "jobName": "IT平台首席AI架构师",
    "jobFamilyName": "质量与流程IT族",
    "deptName": "质量与流程IT部",
    "workPlace": "深圳",
    "cityName": "None",
    "workYear": "5",
    "degree": "None",
    "releaseDate": "None",
    "lastUpdateDate": "2026-10-16",
    "mainBusiness": "标准职责:\n1、主导IT平台领域的AI应用系统架构设计。",
    "jobRequire": "技能要求:\n1、熟悉大模型与智能体。",
    "jobDesc": "None",
}

FINANCE = dict(ITEM, jobId="900001", jobName="财经专员", jobFamilyName="财经族",
               mainBusiness="负责账务处理、月度结账与报表分析。",
               jobRequire="要求熟悉会计准则与税务申报。")


def test_clean_strips_literal_none():
    assert _clean("None") == ""
    assert _clean(None) == ""
    assert _clean(" 深圳 ") == "深圳"
    assert _clean("Nonexistent") == "Nonexistent"


def test_maps_core_fields():
    row = to_rows([ITEM])[0]
    assert row["job_id"] == "hw_114740"
    assert row["company"] == "华为"
    assert row["title"] == "IT平台首席AI架构师"
    assert row["location"] == "深圳"          # cityName 是 "None"，必须回退到 workPlace
    assert row["department"] == "质量与流程IT部"
    assert row["publish_time"] == "2026-10-16"
    assert row["education"] == ""             # degree 是 "None"


def test_jd_merges_duty_and_requirement():
    row = to_rows([ITEM])[0]
    assert "AI应用系统架构设计" in row["jd_text"]
    assert "熟悉大模型与智能体" in row["jd_text"]


def test_tech_family_filter_and_all_mode():
    # 默认只入技术族
    assert to_rows([FINANCE]) == []
    assert len(to_rows([FINANCE], families=None)) == 1
    # 技术族常量包含研发/云服务/流程IT
    assert {"研发族", "云服务族"} <= set(TECH_FAMILIES)


def test_short_jd_and_missing_id_are_skipped():
    short = dict(ITEM, jobId="2", mainBusiness="太短", jobRequire="")
    no_id = dict(ITEM, jobId="")
    assert to_rows([short]) == []
    assert to_rows([no_id]) == []
