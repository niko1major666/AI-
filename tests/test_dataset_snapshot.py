"""语料快照：jobs.jsonl 的规模/字段/来源发生意外变化时立刻报警。

期望值以常量固化；`data/processed/build_stats.json` 是构建产物（目录不入库，
CI 上通常不存在），它在时额外做一次交叉校验，不在时只校验常量，避免测试依赖
未入库文件而在干净克隆上失败。
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

EXPECTED_ROWS = 4776
EXPECTED_COMPANIES = 79
EXPECTED_UNIQUE_COMPANY_TITLE = 4664
REQUIRED_FIELDS = {"job_id", "title", "company", "jd_text"}


@pytest.fixture(scope="module")
def jobs():
    text = JOBS.read_text(encoding="utf-8")
    return [json.loads(x) for x in text.splitlines() if x.strip()]


@pytest.fixture(scope="module")
def stats():
    """构建统计（可选）：`data/processed/` 在 .gitignore 里，干净克隆上没有此文件。"""
    if not STATS.exists():
        return None
    return json.loads(STATS.read_text(encoding="utf-8"))


def test_job_count_snapshot(jobs, stats):
    assert len(jobs) == EXPECTED_ROWS
    if stats is not None:
        assert stats["cleaned_rows"] == len(jobs)


def test_required_fields_and_unique_job_id(jobs):
    for j in jobs[:50]:
        assert REQUIRED_FIELDS <= set(j), f"缺字段：{REQUIRED_FIELDS - set(j)}"
    assert len({j["job_id"] for j in jobs}) == len(jobs)


def test_company_snapshot(jobs, stats):
    companies = {j["company"] for j in jobs}
    assert len(companies) == EXPECTED_COMPANIES
    assert {"腾讯", "字节跳动", "华为"} <= companies
    if stats is not None:
        assert stats["company_count"] == len(companies)


def test_company_title_duplication_rate(jobs):
    unique = {(j["company"], j["title"]) for j in jobs}
    assert len(unique) == EXPECTED_UNIQUE_COMPANY_TITLE


@pytest.mark.slow
def test_full_corpus_extraction_coverage(jobs):
    """全语料抽取（约 10s）：技能覆盖 160/161，零技能岗位约 24.4%。

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
