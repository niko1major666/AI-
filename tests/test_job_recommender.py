from pathlib import Path

from src.matcher.gap_analyzer import SkillGapAnalyzer
from src.matcher.job_recommender import recommend_jobs
from src.skillkb.loader import Taxonomy

ROOT = Path(__file__).resolve().parents[1]
TAX = ROOT / "data" / "kb" / "skill_taxonomy.yaml"


def _analyzer():
    return SkillGapAnalyzer(Taxonomy(str(TAX)))


def _rows():
    return [
        {"company": "A", "title": "大模型算法工程师", "location": "北京",
         "skills": ["AITECH.LLM", "PROG.PYTHON"], "must_skills": ["AITECH.LLM"],
         "skill_tf": {"AITECH.LLM": 3}},
        # 同公司同标题（渠道重复）→ 去重时保留技能更多的第一条
        {"company": "A", "title": "大模型算法工程师 ", "location": "北京",
         "skills": ["AITECH.LLM"], "must_skills": [], "skill_tf": {}},
        {"company": "B", "title": "数据工程师", "location": "上海",
         "skills": ["PROG.SQL", "BIGDATA.SPARK"], "must_skills": ["PROG.SQL"],
         "skill_tf": {}},
        {"company": "C", "title": "零技能岗位", "location": "",
         "skills": [], "must_skills": [], "skill_tf": {}},
    ]


def test_empty_user_skills_returns_empty():
    assert recommend_jobs([], _rows(), _analyzer()) == []


def test_dedup_same_company_and_title():
    res = recommend_jobs(["Python", "大模型"], _rows(), _analyzer(), min_score=0)
    assert [r.title for r in res].count("大模型算法工程师") == 1


def test_score_and_ordering():
    res = recommend_jobs(["Python", "大模型"], _rows(), _analyzer(), min_score=0)
    assert res[0].company == "A"
    assert res[0].match_score == 100.0
    assert res[0].missing_total == 0
    # 数据工程师岗位与简历零交集 → 0 分排最后
    assert res[-1].company == "B"
    assert res[-1].match_score == 0.0


def test_min_score_filters_irrelevant_jobs():
    res = recommend_jobs(["Python"], _rows(), _analyzer(), min_score=1.0)
    assert {r.company for r in res} == {"A"}


def test_top_missing_names():
    res = recommend_jobs(["Python"], _rows(), _analyzer(), min_score=0, top_k=5)
    a = next(r for r in res if r.company == "A")
    assert "大模型" in a.top_missing
    assert len(a.top_missing) <= 3


def test_top_k_and_shortage_of_candidates():
    assert len(recommend_jobs(["Python"], _rows(), _analyzer(), min_score=0, top_k=1)) == 1
    assert recommend_jobs(["Python"], [], _analyzer()) == []


def test_must_weight_affects_score():
    """同样命中 1/2 项时，命中的是硬性要求则分数更高（must 权重 2.0）。"""
    analyzer = _analyzer()
    rows = [
        {"company": "A", "title": "硬性命中", "location": "",
         "skills": ["PROG.PYTHON", "AITECH.RAG"], "must_skills": ["PROG.PYTHON"], "skill_tf": {}},
        {"company": "B", "title": "加分命中", "location": "",
         "skills": ["PROG.PYTHON", "AITECH.RAG"], "must_skills": ["AITECH.RAG"], "skill_tf": {}},
    ]
    res = recommend_jobs(["Python"], rows, analyzer, min_score=0)
    assert res[0].company == "A"
    assert res[0].match_score > res[1].match_score


def test_suggestion_carries_job_id_for_favorites():
    rows = _rows()
    rows[0]["job_id"] = "tx-1"
    rows[0]["last_seen_at"] = "2026-10-26T00:00:00+00:00"
    res = recommend_jobs(["Python", "大模型"], rows, _analyzer(), min_score=0)
    assert res[0].job_id == "tx-1"
    assert res[0].last_seen_at == "2026-10-26T00:00:00+00:00"
