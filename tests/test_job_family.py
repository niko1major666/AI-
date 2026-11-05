"""岗位「技术 / 非技术」判定的回归。

判定顺序很重要：技术标记优先，否则「产品研发工程师」会被「产品」误判成职能岗。
"""

import pytest

from src.data.job_family import classify_title, is_tech_title


@pytest.mark.parametrize(
    "title",
    ["后端开发工程师", "算法工程师（校招）", "Infra 稳定性架构", "Android 开发", "SRE", "大数据开发"],
)
def test_tech_titles(title):
    assert classify_title(title) == "tech"
    assert is_tech_title(title) is True


@pytest.mark.parametrize(
    "title",
    ["内容运营", "产品经理", "税务BP", "合规专员", "市场营销", "校园招聘实习生", "HRBP"],
)
def test_non_tech_titles(title):
    assert classify_title(title) == "non_tech"
    assert is_tech_title(title) is False


def test_tech_marker_wins_over_non_tech_word():
    # 「产品」是职能词，但标题里有「研发/工程师」→ 技术岗
    assert classify_title("产品研发工程师") == "tech"
    assert classify_title("产品设计工程师") == "tech"


def test_unknown_and_empty():
    assert classify_title("") == "unknown"
    assert classify_title(None) == "unknown"
    assert classify_title("管培生") == "unknown"
    assert is_tech_title("管培生") is False
