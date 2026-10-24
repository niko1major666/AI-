"""学习资源库一致性测试（迭代 2）。

约束：报告里缺失技能的资源是「按 skill_id 索引」的，一旦 id 拼错或已合并，
前端就会静默丢失学习建议，因此这里把结构、覆盖与链接格式都锁住。
"""
from pathlib import Path

import yaml

from src.skillkb.loader import Taxonomy

ROOT = Path(__file__).resolve().parents[1]
TAX = ROOT / "data" / "kb" / "skill_taxonomy.yaml"
RES = ROOT / "data" / "kb" / "learning_resources.yaml"
ALLOWED_TYPES = {"course", "book", "paper", "blog", "doc"}


def _res() -> dict:
    return yaml.safe_load(RES.read_text(encoding="utf-8"))


def _entries() -> list:
    return _res()["resources"]


def _tax() -> Taxonomy:
    return Taxonomy(str(TAX))


def test_all_skill_ids_exist_in_taxonomy():
    tax = _tax()
    unknown = [r["skill_id"] for r in _entries() if tax.by_id(r["skill_id"]) is None]
    assert unknown == [], f"资源库存在词表外的 skill_id: {unknown}"


def test_no_duplicate_skill_ids():
    ids = [r["skill_id"] for r in _entries()]
    dups = sorted({i for i in ids if ids.count(i) > 1})
    assert dups == [], f"重复条目会导致后者覆盖前者: {dups}"


def test_coverage_at_least_60_skills():
    tax = _tax()
    covered = {r["skill_id"] for r in _entries()}
    assert len(covered) >= 60
    assert len(covered) / len(tax.all_skills()) >= 0.5


def test_top_demand_skills_have_resources():
    """Top 需求技能（实测占比）必须有学习资源，否则差距报告的高优先级项没建议。"""
    covered = {r["skill_id"] for r in _entries()}
    core = [
        "PROG.PYTHON", "AITECH.LLM", "AITECH.AGENT", "ML.CORE", "PROG.SQL",
        "ML.MULTIMODAL", "ML.VLM", "AITECH.RAG", "AITECH.FUNCALL", "AITECH.MCP",
        "ML.DIFFUSION", "FRAMEWORK.LANGGRAPH", "FRAMEWORK.DIFY",
        "ENGINEERING.ASCEND", "AITECH.QWEN", "AITECH.DEEPSEEK",
    ]
    missing = [s for s in core if s not in covered]
    assert missing == [], f"高频技能缺少学习资源: {missing}"


def test_items_shape_and_urls():
    for r in _entries():
        assert r.get("items"), f"{r['skill_id']} 没有 items"
        for it in r["items"]:
            assert it.get("title", "").strip(), f"{r['skill_id']} 资源缺少 title"
            assert it.get("type") in ALLOWED_TYPES, f"{r['skill_id']} 非法资源类型 {it.get('type')}"
            url = it.get("url", "")
            assert isinstance(url, str)
            # 纸书/内部课程允许留空，其余必须是可点击链接
            assert url == "" or url.startswith(("http://", "https://"))
