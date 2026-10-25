from pathlib import Path

import re

from src.extractor.rule_baseline import RuleBaselineExtractor
from src.skillkb.loader import Taxonomy

TAX = Path(__file__).resolve().parents[1] / "data" / "kb" / "skill_taxonomy.yaml"


def _extractor() -> RuleBaselineExtractor:
    return RuleBaselineExtractor(Taxonomy(str(TAX)))


def test_rule_baseline_extracts_known_skills():
    ex = _extractor()
    text = "熟悉Python、PyTorch、DeepSpeed；了解RAG检索增强、向量数据库、LoRA微调；掌握Transformer与注意力机制。"
    spans = ex.extract_spans("j1", text)
    ids = {s.skill_id for s in spans}
    assert "PROG.PYTHON" in ids
    assert "FRAMEWORK.PYTORCH" in ids
    assert "FRAMEWORK.DEEPSPEED" in ids
    assert "AITECH.RAG" in ids
    assert "AITECH.VECTORDB" in ids
    assert "AITECH.LORA" in ids
    assert "ML.TRANSFORMER" in ids
    assert "ML.ATTENTION" in ids


def test_rule_baseline_ascii_word_boundary():
    ex = _extractor()
    # "go" 不应匹配 "Google"（词边界保护）
    spans = ex.extract_spans("j2", "使用Google搜索")
    assert all(s.skill_id != "PROG.GO" for s in spans)


def test_skip_extract_ignores_noisy_cjk_token():
    """「可量化/量化指标」不得抽成模型量化技能；真正的写法仍要抽到。"""
    ex = _extractor()
    noise = ex.extract_spans("j4", "建立可量化的评估体系，输出量化指标，量化分析业务")
    assert all(s.skill_id != "ML.QUANT" for s in noise)

    real = {s.skill_id for s in ex.extract_spans("j5", "熟悉模型量化与GPTQ、AWQ部署")}
    assert "ML.QUANT" in real


def test_rule_baseline_no_overlap_dup():
    ex = _extractor()
    spans = ex.extract_spans("j3", "熟悉PyTorch")
    ids = [s.skill_id for s in spans]
    # PyTorch 只出现一次，不因别名 torch 重复
    assert ids.count("FRAMEWORK.PYTORCH") == 1



def _regex_reference(text_lower: str, token: str):
    """旧实现（v1.3.0 及之前）的正则版本，作为 _iter_matches 的等价性参照。"""
    if token.isascii():
        pat = r"(?<![a-zA-Z0-9])" + re.escape(token) + r"(?![a-zA-Z0-9])"
    else:
        pat = re.escape(token)
    return [(m.start(), m.end()) for m in re.finditer(pat, text_lower)]


def test_iter_matches_equivalent_to_regex_reference():
    """str.find 实现必须与旧正则逐位置等价（词边界 / 非重叠步进 / 重复出现）。

    换成 find 是为冷启动性能（全语料 24.3s -> 1.5s），但匹配结果不允许有任何变化。
    """
    ex = _extractor()
    texts = [
        "熟悉Python、PyTorch 2.0、TorchScript；了解RAG检索增强与向量数据库，熟练使用 Google 云。",
        "Go / Golang 服务开发；google analytics；c++14 与 c#；Node.js、node 环境。",
        "GOGO 与 go-go, go. Go! 以及 GO 框架；tensorflow 与 tensorflow2。",
        "熟悉 PythonPython 与 python3 以及 Python2.7；PyTorch 和 pytorch-lightning。",
        "课程包括 Cobol、COBOL 与 cobol；HuggingFace Transformers 与 Transformer 模型。",
        "Python与python之间没有空格python3python",
        "",
    ]
    checked = 0
    for text in texts:
        lowered = text.lower()
        for token, _sk in ex._tokens:
            if len(token) < 2:          # extract() 本来就跳过单字符 token
                continue
            assert ex._iter_matches(lowered, token) == _regex_reference(lowered, token), (
                f"token={token!r} text={text!r}"
            )
            checked += 1
    assert checked > 1000


def test_mention_count_respects_word_boundary_and_repeats():
    ex = _extractor()
    # Python9 尾接数字，按词边界规则不算；前两处各计一次
    _, counts = ex.extract("j6", "Python 与 python，再加上 Python9")
    assert counts["PROG.PYTHON"] == 2
    # python3 是词表别名（长 token 先占位），因此只计 1 次，不重复计成 python + python3
    _, counts2 = ex.extract("j7", "熟练使用 python3")
    assert counts2["PROG.PYTHON"] == 1
