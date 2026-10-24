from pathlib import Path

from src.matcher.gap_analyzer import SkillGapAnalyzer
from src.matcher.job_compare import compare_jobs
from src.skillkb.loader import Taxonomy

ROOT = Path(__file__).resolve().parents[1]
TAX = ROOT / "data" / "kb" / "skill_taxonomy.yaml"


def _analyzer():
    return SkillGapAnalyzer(Taxonomy(str(TAX)))


def _jd(*items):
    return [{"skill_id": sid, "name": name, "is_must": must} for sid, name, must in items]


def _target(label, jd, demand=None):
    return {"label": label, "company": "腾讯", "title": label.split()[0],
            "jd_skills": jd, "demand": demand or {}}


def test_compare_reports_score_and_p0_count():
    analyzer = _analyzer()
    res = compare_jobs(analyzer, ["Python"], [
        _target("A 算法", _jd(("PROG.PYTHON", "Python", True),
                              ("FRAMEWORK.PYTORCH", "PyTorch", True))),
        _target("B 算法", _jd(("PROG.PYTHON", "Python", True),
                              ("AITECH.LLM", "大模型", True),
                              ("AITECH.RAG", "RAG", True))),
    ])
    assert len(res.jobs) == 2
    by_label = {j.label: j for j in res.jobs}
    assert by_label["A 算法"].match_score == 50.0     # 1/2 must
    assert by_label["A 算法"].p0_total == 1
    assert by_label["B 算法"].match_score == 33.3     # 1/3 must
    assert by_label["B 算法"].p0_total == 2
    assert res.best_label == "A 算法"


def test_common_and_unique_missing():
    analyzer = _analyzer()
    res = compare_jobs(analyzer, ["Python"], [
        _target("A", _jd(("PROG.PYTHON", "Python", True),
                         ("FRAMEWORK.PYTORCH", "PyTorch", True),
                         ("AITECH.RAG", "RAG", False))),
        _target("B", _jd(("PROG.PYTHON", "Python", True),
                         ("FRAMEWORK.PYTORCH", "PyTorch", True),
                         ("ML.TRANSFORMER", "Transformer", False))),
    ])
    assert res.common_missing == ["PyTorch"]
    assert res.unique_missing["A"] == ["RAG"]
    assert res.unique_missing["B"] == ["Transformer"]


def test_single_target_has_no_unique_missing():
    analyzer = _analyzer()
    res = compare_jobs(analyzer, [], [
        _target("A", _jd(("AITECH.RAG", "RAG", True))),
    ])
    assert res.unique_missing == {"A": []}
    assert res.common_missing == ["RAG"]


def test_empty_targets_returns_empty_result():
    res = compare_jobs(_analyzer(), ["Python"], [])
    assert res.jobs == [] and res.common_missing == [] and res.best_label == ""


def test_best_label_prefers_higher_score_then_fewer_missing():
    analyzer = _analyzer()
    res = compare_jobs(analyzer, ["Python"], [
        _target("低", _jd(("PROG.PYTHON", "Python", True),
                          ("AITECH.LLM", "大模型", True),
                          ("AITECH.RAG", "RAG", True))),
        _target("高", _jd(("PROG.PYTHON", "Python", True))),
    ])
    assert res.best_label == "高"
