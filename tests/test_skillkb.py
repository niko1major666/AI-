from pathlib import Path

from src.skillkb.loader import Taxonomy

TAX = Path(__file__).resolve().parents[1] / "data" / "kb" / "skill_taxonomy.yaml"


def _tax() -> Taxonomy:
    return Taxonomy(str(TAX))


def test_load_counts():
    t = _tax()
    # 147 + 迭代 2 新增 16（MCP/Function Calling/扩散模型/VLM/…）- 合并 2（文本向量化、华为云）
    assert len(t.all_skills()) == 161
    assert len(t.categories) == 6


def test_iter2_new_skills_resolve():
    """迭代 2 新增技能可按名称/别名解析（原来这些词在 JD 里完全抽不到）。"""
    t = _tax()
    cases = {
        "MCP": "AITECH.MCP",
        "模型上下文协议": "AITECH.MCP",
        "Function Calling": "AITECH.FUNCALL",
        "工具调用": "AITECH.FUNCALL",
        "具身智能": "AITECH.EMBODIED",
        "世界模型": "AITECH.WORLDMODEL",
        "Qwen": "AITECH.QWEN",
        "通义千问": "AITECH.QWEN",
        "DeepSeek": "AITECH.DEEPSEEK",
        "Llama": "AITECH.LLAMA",
        "GLM": "AITECH.GLM",
        "DPO": "AITECH.DPO",
        "GRPO": "AITECH.DPO",
        "视频生成": "AITECH.VIDEOGEN",
        "长上下文": "AITECH.LONGCONTEXT",
        "扩散模型": "ML.DIFFUSION",
        "视觉语言模型": "ML.VLM",
        "多模态大模型": "ML.VLM",
        "LangGraph": "FRAMEWORK.LANGGRAPH",
        "Dify": "FRAMEWORK.DIFY",
        "扣子": "FRAMEWORK.DIFY",
        "昇腾": "ENGINEERING.ASCEND",
    }
    for text, want in cases.items():
        got = t.resolve(text)
        assert got is not None, f"{text} 未命中词表"
        assert got.id == want, f"{text} -> {got.id}，期望 {want}"


def test_iter2_merged_redundant_skills():
    """零命中冗余技能合并到同义技能，别名仍可解析（避免出现无人引用的 id）。"""
    t = _tax()
    assert t.by_id("AITECH.TEXTVEC") is None
    assert t.by_id("ENGINEERING.HUAWEICLOUD") is None
    assert t.resolve("文本向量化").id == "AITECH.EMBEDDING"
    assert t.resolve("文本向量").id == "AITECH.EMBEDDING"
    assert t.resolve("华为云").id == "ENGINEERING.CLOUD"
    # 真实存在但语料未出现的技能保留（不为了覆盖率删技能）
    assert t.by_id("ML.FED") is not None


def test_quantization_aliases():
    """「模型量化 / GPTQ / AWQ」归到已有量化技能；裸「量化」仅用于用户输入解析。"""
    t = _tax()
    for text in ["模型量化", "GPTQ", "AWQ", "quantization", "量化"]:
        assert t.resolve(text).id == "ML.QUANT"
    assert "量化" in t.by_id("ML.QUANT").skip_extract


def test_unittest_alias_only_for_user_input():
    """裸「测试」保留给简历/手输解析，但不参与 JD 抽取（JD 里多为 A/B 测试等噪声）。"""
    t = _tax()
    assert t.resolve("测试").id == "ENGINEERING.UNITTEST"
    assert t.resolve("单元测试").id == "ENGINEERING.UNITTEST"
    assert "测试" in t.by_id("ENGINEERING.UNITTEST").skip_extract


def test_resolve_exact_name():
    t = _tax()
    assert t.resolve("Python").id == "PROG.PYTHON"
    assert t.resolve("pytorch").id == "FRAMEWORK.PYTORCH"
    assert t.resolve("向量数据库").id == "AITECH.VECTORDB"
    assert t.resolve("分布式训练").id == "AITECH.DISTRIBUTED"


def test_resolve_alias():
    t = _tax()
    assert t.resolve("多卡训练").id == "AITECH.DISTRIBUTED"
    assert t.resolve("飞桨").id == "FRAMEWORK.PADDLE"


def test_resolve_fuzzy():
    t = _tax()
    assert t.resolve("pytho").id == "PROG.PYTHON"


def test_resolve_unknown_none():
    t = _tax()
    assert t.resolve("zzzzz不存在的技能") is None


def test_by_id():
    t = _tax()
    assert t.by_id("AITECH.RAG").name == "RAG"
    assert t.by_id("NOPE") is None


def test_importance_field():
    t = _tax()
    # 高频技能重要度高（数据驱动：按 JD 需求占比，当前语料 5163 条 / 80 家）
    assert t.by_id("PROG.PYTHON").importance == 5
    assert t.by_id("FRAMEWORK.PYTORCH").importance == 5
    assert t.by_id("AITECH.LLM").importance == 5
    assert t.by_id("AITECH.AGENT").importance == 5
    # 中高频技能
    assert t.by_id("AITECH.RAG").importance == 4
    assert t.by_id("ML.RL").importance == 4
    # 低频技能重要度低（占比 <1% → 1）
    assert t.by_id("AITECH.KG").importance == 1
    # 中等频次（2%~5% → 3）
    assert t.by_id("BIGDATA.FLINK").importance == 3
    # 数据标注：高频但低门槛（难度低），importance 反映需求频率
    assert t.by_id("AITECH.ANNOTATE").importance == 3
