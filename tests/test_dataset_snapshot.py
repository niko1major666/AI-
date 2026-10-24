"""语料快照：jobs.jsonl 的规模/字段/来源发生意外变化时立刻报警。

这些数字来自 `data/processed/build_stats.json`（构建产物自带统计），
如果确实换了数据源，需要同步更新这里与 build_stats，避免「静默换数据」。
"""
import json
from pathlib import Path

import pytest

from src.extractor.rule_baseline import RuleBaselineExtractor
from src.skillkb.loader import Taxonomy

ROOT = Path(__file__).resolve().parents[1]
JOBS = ROOT / "data" / "processed" / "jobs.jsonl"
STATS = ROOT / "data" / "processed" / "build_stats.json"
TAX = ROOT / "data" / "kb" / "skill_taxonomy.yaml"

EXPECTED_ROWS = 4582
EXPECTED_COMPANIES = 78
EXPECTED_UNIQUE_COMPANY_TITLE = 4472
REQUIRED_FIELDS = {"job_id", "title", "company", "jd_text"}


@pytest.fixture(scope="module")
def jobs():
    text = JOBS.read_text(encoding="utf-8")
    return [json.loads(x) for x in text.splitlines() if x.strip()]


def test_job_count_matches_build_stats(jobs):
    stats = json.loads(STATS.read_text(encoding="utf-8"))
    assert stats["cleaned_rows"] == EXPECTED_ROWS
    assert len(jobs) == EXPECTED_ROWS


def test_required_fields_and_unique_job_id(jobs):
    for j in jobs[:50]:
        assert REQUIRED_FIELDS <= set(j), f"缺字段：{REQUIRED_FIELDS - set(j)}"
    assert len({j["job_id"] for j in jobs}) == len(jobs)


def test_company_snapshot(jobs):
    companies = {j["company"] for j in jobs}
    assert len(companies) == EXPECTED_COMPANIES
    stats = json.loads(STATS.read_text(encoding="utf-8"))
    assert stats["company_count"] == EXPECTED_COMPANIES
    assert {"腾讯", "字节跳动", "华为"} <= companies


def test_company_title_duplication_rate(jobs):
    unique = {(j["company"], j["title"]) for j in jobs}
    assert len(unique) == EXPECTED_UNIQUE_COMPANY_TITLE


@pytest.mark.slow
def test_full_corpus_extraction_coverage(jobs):
    """全语料抽取（约 10s）：技能覆盖 160/161，零技能岗位约 23.7%。

    标记 slow：PR 只跑快测，nightly 跑全量（见 .github/workflows/nightly.yml）。
    """
    tax = Taxonomy(str(TAX))
    rule = RuleBaselineExtractor(tax)
    hit, zero = set(), 0
    for j in jobs:
        ids = {s.skill_id for s in rule.extract_spans(
            j["job_id"], j.get("jd_clean") or j.get("jd_text", ""))}
        if not ids:
            zero += 1
        hit |= ids
    assert len(hit) >= 159, f"语料技能覆盖下降：{len(hit)}/{len(tax.all_skills())}"
    ratio = zero / len(jobs)
    assert 0.20 <= ratio <= 0.28, f"零技能岗位占比异常：{ratio:.1%}"
