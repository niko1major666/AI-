"""岗位相关性判定的回归。

规则经过抽样验证（规则 vs 千问：131/131 一致），这里锁住那些容易判错的边界，
避免以后调词表时把「AI Operations Lead」判成技术岗、把「Tech Lead」误杀。
"""

import pytest

from src.data.job_relevance import decide, is_target


@pytest.mark.parametrize(
    "title",
    ["后端开发工程师", "算法工程师（校招）", "Android 开发", "大数据开发", "SRE"],
)
def test_chinese_tech_targets(title):
    assert decide(title) == "target"


@pytest.mark.parametrize(
    "title",
    ["内容运营", "税务BP", "合规专员", "校园招聘实习生", "产品经理"],
)
def test_chinese_non_targets(title):
    assert decide(title) == "non_target"


@pytest.mark.parametrize(
    "title",
    [
        "Machine Learning Engineer",
        "Senior AI Engineer - Legal AI",
        "Staff Marketing Technology Engineer",
        "Tech Lead, Autonomy Systems",
        "Data Engineer",
        "Software Development Engineer",
    ],
)
def test_english_tech_targets(title):
    assert decide(title) == "target", title


@pytest.mark.parametrize(
    "title",
    [
        "AI Operations Lead",
        "Director, GTM Engineering",
        "Senior AI Product Manager",
        "Senior Product Manager (APIs & Data Sharing)",
        "Battery Test Engineer",
        "Electronics Technician",
        "Biomechanics Researcher",
        "Internship Bioengineering / Molecular Biology",
        "Recruiter",
    ],
)
def test_english_non_targets(title):
    assert decide(title) == "non_target", title


def test_unknown_kept_by_default():
    assert decide("管培生") == "uncertain"
    assert is_target("管培生") is True
    assert is_target("AI Operations Lead") is False
