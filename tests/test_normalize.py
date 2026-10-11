import pytest

from src.data.normalize import clean_text, normalize_company, parse_salary, sha1_text


def test_clean_text_strips_html():
    assert clean_text("<p>熟悉 <b>PyTorch</b></p>") == "熟悉 PyTorch"


def test_clean_text_removes_urls_and_collapses_space():
    out = clean_text("见官网 https://example.com/a  详见\n说明")
    assert "example.com" not in out
    assert "\n" not in out
    assert "  " not in out


def test_normalize_company_strips_suffix():
    assert normalize_company("华为技术有限公司") == "华为技术"
    assert normalize_company("科大讯飞股份有限公司") == "科大讯飞"


def test_normalize_company_strips_parenthetical():
    assert normalize_company("阿里巴巴（中国）有限公司") == "阿里巴巴"


def test_parse_salary_k_month():
    assert parse_salary("30-60K·15薪") == (30.0, 60.0, 15)


def test_parse_salary_plain_k():
    assert parse_salary("25-50K") == (25.0, 50.0, None)


def test_parse_salary_annual():
    lo, hi, m = parse_salary("年薪30-50万")
    assert lo == pytest.approx(25.0, abs=0.1)
    assert hi == pytest.approx(41.7, abs=0.1)
    assert m is None


def test_parse_salary_wan_month():
    assert parse_salary("3-5万·13薪") == (30.0, 50.0, 13)


def test_parse_salary_yuan_month():
    assert parse_salary("20000-40000元/月") == (20.0, 40.0, None)


def test_parse_salary_negotiable():
    assert parse_salary("面议") == (None, None, None)
    assert parse_salary("") == (None, None, None)


def test_sha1_stable():
    assert sha1_text("abc") == sha1_text("abc")
    assert sha1_text("abc") != sha1_text("abd")
