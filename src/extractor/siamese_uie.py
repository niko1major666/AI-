"""SiameseUIE 零样本技能抽取。

用法：
    python -m src.extractor.siamese_uie --demo          # 内置样例
    python -m src.extractor.siamese_uie --jobs data/processed/jobs.jsonl --max-jobs 3
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

import yaml

from src.extractor import postprocess
from src.skillkb.loader import Taxonomy

DEFAULT_MODEL = "damo/nlp_structbert_siamese-uie_chinese-base"


def _patch_siamese_uie_init():
    """修复 ModelScope 缺陷：SiameseUiePipeline.__init__ 未把 trust_remote_code
    转发给基类，导致带 allow_remote/plugins 字段的官方模型被安全拦截而无法加载。
    此处重写 __init__，将全部 kwargs（含 trust_remote_code）转发给基类。幂等。"""
    from modelscope.models.base import Model
    from modelscope.pipelines.base import Pipeline
    from modelscope.pipelines.nlp.siamese_uie_pipeline import SiameseUiePipeline
    from modelscope.preprocessors import Preprocessor

    if getattr(SiameseUiePipeline, "_trust_patched", False):
        return

    def __init__(self, model, preprocessor=None, config_file=None, device="cpu",
                 auto_collate=True, **kwargs):
        Pipeline.__init__(
            self, model=model, preprocessor=preprocessor, config_file=config_file,
            device=device, auto_collate=auto_collate, **kwargs)
        assert isinstance(self.model, Model), \
            "please check whether model config exists in configuration.json"
        kwargs.pop("compile", None)
        kwargs.pop("compile_options", None)
        if self.preprocessor is None:
            self.preprocessor = Preprocessor.from_pretrained(self.model.model_dir, **kwargs)
        self.model.eval()
        self.slide_len = 352
        self.max_len = 384
        self.hint_max_len = 128
        self.inference_batch_size = 8
        self.threshold = 0.5

    SiameseUiePipeline.__init__ = __init__
    SiameseUiePipeline._trust_patched = True


DEMO_TEXTS = [
    "负责大模型预训练与微调。熟悉Python、PyTorch、DeepSpeed；了解RAG检索增强、向量数据库、LoRA微调；深入理解Transformer与注意力机制。",
    "负责计算机视觉算法研发。熟悉Python、TensorFlow；掌握目标检测、图像分割；有分布式训练经验者优先。",
    "负责推荐系统。熟悉Spark、Hadoop、SQL；掌握图神经网络、特征工程、向量检索；了解Kubernetes、Docker。",
]


class SiameseUIEExtractor:
    """惰性加载 ModelScope SiameseUIE pipeline。"""

    def __init__(self, model_id: str = DEFAULT_MODEL, device: str = "cpu",
                 model_revision: str = "master", trust_remote_code: bool = True):
        self.model_id = model_id
        self.device = device
        self.model_revision = model_revision
        self.trust_remote_code = trust_remote_code
        self._pipe = None

    def _load(self):
        if self._pipe is None:
            from modelscope.pipelines import pipeline
            from modelscope.utils.constant import Tasks

            _patch_siamese_uie_init()
            self._pipe = pipeline(
                Tasks.siamese_uie,
                model=self.model_id,
                model_revision=self.model_revision,
                device=self.device,
                trust_remote_code=self.trust_remote_code,
            )
        return self._pipe

    def extract_raw(self, text: str, schema: dict) -> dict:
        """返回 {类型: [实体...]}，实体为 str 或 dict。"""
        pipe = self._load()
        result = pipe(input=text, schema=schema)
        return _flatten(result)

    def extract_spans(self, job_id: str, text: str, schema: dict, taxonomy: Taxonomy,
                      conf_threshold: float = 0.0, method: str = "siamese_uie"):
        raw = self.extract_raw(text, schema)
        return postprocess.to_skill_spans(job_id, raw, taxonomy, method=method,
                                          conf_threshold=conf_threshold)


def _flatten(result) -> dict:
    """把 SiameseUIE 输出规整成 {类型: [{'text','start','end'}...]}。

    实测输出：{'output': [[{'type':'人物','span':'x','offset':[a,b]}], ...]}
    """
    out: dict = {}
    if isinstance(result, dict):
        payload = result.get("output", result)
    else:
        payload = result

    def walk(x):
        if isinstance(x, dict):
            yield x
        elif isinstance(x, (list, tuple)):
            for i in x:
                yield from walk(i)

    for ent in walk(payload):
        typ = ent.get("type") or ent.get("类型")
        span = ent.get("span") or ent.get("text") or ent.get("name")
        if not typ or not span:
            continue
        off = ent.get("offset")
        if isinstance(off, (list, tuple)) and len(off) == 2:
            start, end = off[0], off[1]
        else:
            start, end = ent.get("start"), ent.get("end")
        out.setdefault(typ, []).append({"text": span, "start": start, "end": end})
    return out


def _load_config(path: Optional[str]) -> dict:
    root = Path(__file__).resolve().parents[2]
    return yaml.safe_load((root / (path or "configs/extraction.yaml")).read_text(encoding="utf-8"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="SiameseUIE 技能抽取")
    ap.add_argument("--demo", action="store_true", help="用内置样例演示")
    ap.add_argument("--config", default=None)
    ap.add_argument("--jobs", default=None, help="jobs.jsonl 路径")
    ap.add_argument("--max-jobs", type=int, default=3)
    args = ap.parse_args(argv)

    root = Path(__file__).resolve().parents[2]
    cfg = _load_config(args.config)
    ext_cfg = cfg["extractor"]
    schema = {t: None for t in cfg["schema"]}
    taxonomy = Taxonomy(str(root / cfg["postprocess"]["taxonomy_path"]))

    from src.extractor.rule_baseline import RuleBaselineExtractor
    rule_extractor = RuleBaselineExtractor(taxonomy)

    extractor = SiameseUIEExtractor(
        model_id=ext_cfg["model_id"],
        device=ext_cfg.get("device", "cpu"),
        model_revision=ext_cfg.get("model_revision", "master"),
    )
    conf = float(ext_cfg.get("conf_threshold", 0.0))

    if args.jobs:
        lines = Path(args.jobs).read_text(encoding="utf-8").splitlines()
        jobs = [json.loads(x) for x in lines][: args.max_jobs]
        texts = [(j["job_id"], j.get("jd_clean") or j.get("jd_text", "")) for j in jobs]
    else:
        texts = [(f"demo_{i}", t) for i, t in enumerate(DEMO_TEXTS)]

    for job_id, text in texts:
        rule_spans = rule_extractor.extract_spans(job_id, text)
        uie_spans = extractor.extract_spans(job_id, text, schema, taxonomy, conf_threshold=conf)
        print(f"\n===== {job_id} =====")
        print("  [规则基线/词表匹配]")
        for s in rule_spans:
            print(f"    [{s.category}] {s.skill_text:<20} -> {s.skill_id:<28}")
        print("  [SiameseUIE 零样本]")
        for s in uie_spans:
            print(f"    [{s.category}] {s.skill_text:<20} -> {s.skill_id:<28} (score={s.score})")
        if not rule_spans and not uie_spans:
            print("    (无结果)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
