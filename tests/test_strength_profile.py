from pathlib import Path

from src.matcher.strength_profile import (
    category_profile,
    overall_coverage,
    weakest_categories,
)
from src.skillkb.loader import Taxonomy

ROOT = Path(__file__).resolve().parents[1]
TAX = ROOT / "data" / "kb" / "skill_taxonomy.yaml"


def _tax():
    return Taxonomy(str(TAX))


def test_profile_covers_every_category_in_taxonomy_order():
    tax = _tax()
    profile = category_profile(["PROG.PYTHON"], tax, {"PROG.PYTHON": 0.4})
    assert [p["category"] for p in profile] == [c[0] for c in tax.categories]
    prog = next(p for p in profile if p["category"] == "PROG")
    assert prog["owned"] == 1
    assert prog["total"] == len([s for s in tax.all_skills() if s.category == "PROG"])


def test_coverage_is_demand_weighted():
    tax = _tax()
    high = category_profile(["PROG.PYTHON"], tax, {"PROG.PYTHON": 1.0})
    low = category_profile(["PROG.PYTHON"], tax, {"PROG.PYTHON": 0.01})
    c_high = next(p["coverage"] for p in high if p["category"] == "PROG")
    c_low = next(p["coverage"] for p in low if p["category"] == "PROG")
    assert 0.9 < c_high < 1.0          # 其余技能按 0.001 计入分母
    assert c_low < 0.5                 # 掌握的是冷门技能 → 覆盖率低


def test_empty_user_gives_zero_coverage():
    tax = _tax()
    profile = category_profile([], tax, {"PROG.PYTHON": 1.0})
    assert all(p["coverage"] == 0.0 for p in profile)
    assert overall_coverage([], tax, {"PROG.PYTHON": 1.0}) == 0.0


def test_overall_coverage_between_zero_and_one():
    tax = _tax()
    cov = overall_coverage(["PROG.PYTHON", "AITECH.RAG"], tax, {"PROG.PYTHON": 0.4, "AITECH.RAG": 0.2})
    assert 0.0 < cov < 1.0


def test_top_missing_is_limited_and_sorted_by_demand():
    tax = _tax()
    demand = {"ML.DL": 0.5, "ML.CORE": 0.2, "ML.TRANSFORMER": 0.1}
    profile = category_profile([], tax, demand, top_missing=2)
    ml = next(p for p in profile if p["category"] == "ML")
    assert ml["top_missing"][0] == "深度学习"
    assert len(ml["top_missing"]) == 2


def test_weakest_categories_sorted_ascending():
    tax = _tax()
    profile = category_profile(["PROG.PYTHON", "AITECH.RAG"], tax,
                               {"PROG.PYTHON": 0.5, "AITECH.RAG": 0.3})
    weak = weakest_categories(profile, limit=3)
    assert len(weak) == 3
    assert weak[0]["coverage"] <= weak[-1]["coverage"]
