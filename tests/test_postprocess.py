from pathlib import Path

from src.extractor import postprocess
from src.skillkb.loader import Taxonomy

TAX = Path(__file__).resolve().parents[1] / "data" / "kb" / "skill_taxonomy.yaml"


def _tax() -> Taxonomy:
    return Taxonomy(str(TAX))


def test_strip_version():
    assert postprocess.strip_version("Python 3.8") == "Python"
    assert postprocess.strip_version("PyTorch 2.0") == "PyTorch"
    assert postprocess.strip_version("Transformer") == "Transformer"


def test_normalize_skill():
    assert postprocess.normalize_skill("  PyTorch ") == "pytorch"
    assert postprocess.normalize_skill("分布式 训练") == "分布式训练"


def test_to_skill_spans_resolves_known():
    tax = _tax()
    typed = {
        "编程语言": ["Python", "C++"],
        "深度学习框架": ["PyTorch", "TensorFlow"],
        "AI专有技术": ["分布式训练", "向量数据库", "LoRA"],
    }
    spans = postprocess.to_skill_spans("j1", typed, tax, method="siamese_uie")
    ids = {s.skill_id for s in spans}
    assert "PROG.PYTHON" in ids
    assert "PROG.CPP" in ids
    assert "FRAMEWORK.PYTORCH" in ids
    assert "AITECH.DISTRIBUTED" in ids
    assert "AITECH.VECTORDB" in ids
    assert "AITECH.LORA" in ids


def test_to_skill_spans_unresolved():
    tax = _tax()
    typed = {"AI专有技术": ["某个冷门新工具XYZ"]}
    spans = postprocess.to_skill_spans("j2", typed, tax, method="siamese_uie")
    assert len(spans) == 1
    assert spans[0].skill_id.startswith("UNRESOLVED.")


def test_to_skill_spans_dedup():
    tax = _tax()
    typed = {"编程语言": ["Python", "python", "Python 3.8"]}
    spans = postprocess.to_skill_spans("j3", typed, tax, method="siamese_uie")
    assert len(spans) == 1
    assert spans[0].skill_id == "PROG.PYTHON"


def test_unwrap_dict_entity():
    assert postprocess._unwrap({"text": "PyTorch", "score": 0.9, "start": 0, "end": 7}) == \
        ("PyTorch", 0.9, 0, 7)
    assert postprocess._unwrap("Python") == ("Python", 1.0, None, None)
