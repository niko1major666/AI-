"""新数据源接入前体检（只读：不写库、不改数据）。

为什么需要它 —— 语料一变，会同时踩到两类坑：

- **一定会红**：`tests/test_dataset_snapshot.py` 的精确常量（4582 / 78 / 4472）、slow 用例的
  「零技能占比 20%~28% + 技能覆盖 ≥159」、CI 对 `docs/metrics.md` 的过期校验
  （`git diff --exit-code`）、`tests/test_skillkb.py` 的 importance 断言；
- **静默出错**：job_id 撞车被 `merge_jobs` 的 keep=first 丢行、正文跨源重复让公司归属取决于
  `FILES` 顺序、公司别名不合并（「阿里」与「阿里巴巴」算两家）、整站列表式短 JD 让零技能
  兜底失效、标题过滤词表不够导致传统岗位混入。

所以在跑 `merge_jobs.py` / `build_dataset` 之前，先用这个脚本把「合并后会发生什么」推演一遍。
检查项与判定阈值见 `memory-bank/dataOnboarding.md`。

用法：
    python scripts/preflight_new_source.py --source data/raw/ali_ai_jobs.csv
    python scripts/preflight_new_source.py --source a.csv --source b.csv --json preflight.json
    python scripts/preflight_new_source.py --source a.csv --zero-skill-band 0.20,0.28

退出码：存在 FAIL → 1；只有 PASS / WARN → 0（WARN 需人工确认，确认后再跑合并与构建）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data import job_filter, load_kaggle, normalize  # noqa: E402
from src.extractor.rule_baseline import RuleBaselineExtractor  # noqa: E402
from src.matcher.jd_requirements import judge_requirements  # noqa: E402
from src.skillkb.loader import Taxonomy  # noqa: E402

DEFAULT_JOBS = ROOT / "data" / "processed" / "jobs.jsonl"
DEFAULT_CONFIG = ROOT / "configs" / "dataset.yaml"
DEFAULT_TAXONOMY = ROOT / "data" / "kb" / "skill_taxonomy.yaml"

REQUIRED_FIELDS = ("job_id", "company", "title", "jd_text")
# ★ 这两个阈值与 tests/test_dataset_snapshot.py 的 slow 用例保持一致：
#   改测试常量时同步改这里，或在命令行用 --zero-skill-band / --min-skill-coverage 覆盖。
ZERO_SKILL_BAND = (0.20, 0.28)
MIN_SKILL_COVERAGE = 159
MUST_RATIO_TOLERANCE = 0.03      # 合并后 must 占比相对现有语料的允许偏移
HIGH_ZERO_SKILL_COMPANY = 0.30   # 单公司零技能率告警线（快手 32.5% / 小红书 37.4% 属已知）
_SKILLS_COLUMNS = ("skills", "skill", "技能", "技能要求")
_SKILL_SPLIT_RE = re.compile(r"[,，、;；/|]+")


def _utf8_stdout() -> None:
    """CI / PowerShell 下保证中文输出不乱码；pytest 捕获的 stdout 没有 reconfigure 时跳过。"""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


def load_config(config_path=DEFAULT_CONFIG) -> tuple[dict, dict]:
    """读 dataset.yaml，返回 (column_mapping, 完整配置)。"""
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    return cfg.get("column_mapping") or {}, cfg


def load_source(paths, mapping, *, min_jd_chars: int = 30, title_filter: bool = True,
                exclude_keywords=None, keep_keywords=None) -> dict:
    """按 `build_dataset` 的口径读取并清洗新 CSV（不落库）。

    返回 {"rows": [...], "stats": {...}}；清洗规则与构建阶段一致（空正文 → 过短 → 标题过滤），
    这样体检结果才能代表「这批数据真正会进语料的部分」。
    """
    rows: list[dict] = []
    stats: dict = {
        "files": [str(p) for p in paths], "raw_rows": 0, "dropped_short": 0,
        "dropped_offtopic": 0, "empty_text": 0, "missing_job_id": 0,
        "dup_job_id_in_source": 0, "empty_required": {},
    }
    seen_ids: set[str] = set()
    for path in paths:
        df = load_kaggle.load_dataframe(str(path), mapping)
        stats["raw_rows"] += len(df)
        for col in load_kaggle.CANONICAL:
            if col not in df.columns:
                df[col] = ""
        for field in REQUIRED_FIELDS:
            if not df[field].astype(str).str.strip().any():
                stats["empty_required"][field] = stats["empty_required"].get(field, 0) + 1
        for _, rec in df.iterrows():
            text = normalize.clean_text(rec["jd_text"])
            if not text:
                stats["empty_text"] += 1
                continue
            if len(text) < min_jd_chars:
                stats["dropped_short"] += 1
                continue
            title = str(rec["title"] or "").strip()
            if title_filter and job_filter.is_offtopic_title(title, exclude_keywords, keep_keywords):
                stats["dropped_offtopic"] += 1
                continue
            job_id = str(rec["job_id"] or "").strip()
            if not job_id:
                stats["missing_job_id"] += 1
            elif job_id in seen_ids:
                stats["dup_job_id_in_source"] += 1
            seen_ids.add(job_id)
            company = str(rec["company"] or "").strip()
            rows.append({
                "job_id": job_id,
                "company": company,
                "company_norm": normalize.normalize_company(company),
                "title": title,
                "text": text,
                "text_hash": normalize.sha1_text(text),
                "skills": [], "skill_spans": [], "skill_tf": {},
                "source_file": Path(path).name,
            })
    return {"rows": rows, "stats": stats}


def load_existing(path=DEFAULT_JOBS) -> list[dict]:
    """读现有语料 jobs.jsonl（只取体检需要的字段；文件缺失时返回空列表）。"""
    p = Path(path)
    if not p.exists():
        return []
    rows: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        text = obj.get("jd_clean") or obj.get("jd_text") or ""
        rows.append({
            "job_id": str(obj.get("job_id") or ""),
            "company": str(obj.get("company") or ""),
            "company_norm": str(obj.get("company_norm")
                                or normalize.normalize_company(obj.get("company") or "")),
            "title": str(obj.get("title") or ""),
            "text": text,
            "text_hash": str(obj.get("text_hash") or normalize.sha1_text(text)),
            "skills": [], "skill_spans": [], "skill_tf": {},
            "source_file": "jobs.jsonl",
        })
    return rows


def check_identity(new_rows, existing_rows) -> dict:
    """job_id 体检：`merge_jobs` 按 job_id keep=first，撞车会静默丢行。"""
    existing_ids = {r["job_id"] for r in existing_rows if r["job_id"]}
    new_ids = [r["job_id"] for r in new_rows if r["job_id"]]
    dup = sorted(k for k, v in Counter(new_ids).items() if v > 1)
    collide = sorted(set(new_ids) & existing_ids)
    return {
        "total": len(new_rows),
        "missing": sum(1 for r in new_rows if not r["job_id"]),
        "dup_in_new_count": len(dup),
        "dup_in_new": dup[:10],
        "collision_count": len(collide),
        "collisions": collide[:10],
        # 建议带源前缀（ks_ / kimi_ / hw51_）：裸数字 id 最容易撞
        "unprefixed_collisions": [j for j in collide if "_" not in j][:10],
    }


def check_text(new_rows, existing_rows) -> dict:
    """正文体检：`build_dataset` 按 text_hash keep=first，FILES 顺序决定谁留、公司归谁。"""
    existing_hash = {r["text_hash"] for r in existing_rows}
    counter = Counter(r["text_hash"] for r in new_rows)
    new_hash = set(counter)
    overlap = new_hash & existing_hash
    dup_hashes = [h for h, c in counter.items() if c > 1]
    return {
        "dup_in_new_count": len(dup_hashes),
        "dup_in_new_rows": sum(counter[h] - 1 for h in dup_hashes),
        "overlap_count": len(overlap),
        # 新源追加在 FILES 末尾（推荐）：这些重复行会被丢掉
        "dropped_if_new_last": sum(counter[h] for h in overlap),
        # 新源放在最前：现有语料里同文行会被覆盖掉（公司归属可能被改写）
        "dropped_if_new_first": sum(1 for r in existing_rows if r["text_hash"] in new_hash),
        "overlap_samples": [r["title"] for r in new_rows if r["text_hash"] in overlap][:5],
    }


def check_company(new_rows, existing_rows) -> dict:
    """公司体检：归一函数只去后缀/括号/小写，不做别名合并（「阿里」≠「阿里巴巴」）。"""
    def _group(rows):
        grouped: dict[str, set] = defaultdict(set)
        for r in rows:
            if r["company_norm"]:
                grouped[r["company_norm"]].add(r["company"])
        return grouped

    gnew, gexist = _group(new_rows), _group(existing_rows)
    variants_cross = {k: {"existing": sorted(gexist[k]), "new": sorted(gnew[k])}
                      for k in set(gnew) & set(gexist) if gnew[k] != gexist[k]}
    variants_inner = {k: sorted(v) for k, v in gnew.items() if len(v) > 1}
    added = sorted(gnew.keys() - gexist.keys())
    return {
        "new_company_norms": len(gnew),
        "existing_company_count": len(gexist),
        "added_company_count": len(added),
        "added_companies": added[:10],
        "variants_cross_count": len(variants_cross),
        "variants_cross": dict(list(variants_cross.items())[:10]),
        "variants_inner_count": len(variants_inner),
        "variants_inner": dict(list(variants_inner.items())[:10]),
    }


def extract_rows(rows, rule) -> None:
    """给每行补 skills / skill_spans / skill_tf（幂等：已抽过的行跳过）。"""
    for r in rows:
        if r.get("_extracted"):
            continue
        spans, counts = rule.extract(r["job_id"] or "preflight", r["text"])
        r["skills"] = [s.skill_id for s in spans]
        r["skill_spans"] = [(s.skill_id, s.start) for s in spans]
        r["skill_tf"] = counts
        r["_extracted"] = True


def compute_demand(rows) -> dict:
    """全行业需求占比（与 `src/app/app.py` 的 compute_demand 同口径：按岗位去重计数）。"""
    total = len(rows)
    if not total:
        return {}
    counter: Counter = Counter()
    for r in rows:
        for sid in set(r["skills"]):
            counter[sid] += 1
    return {sid: c / total for sid, c in counter.items()}


def zero_skill_stats(rows, top_n: int = 8) -> dict:
    """零技能岗位占比（整体 + 单公司，用于判断新源是否会让兜底失效）。"""
    per: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in rows:
        key = r["company"] or "<无公司>"
        per[key][0] += 1
        if not r["skills"]:
            per[key][1] += 1
    total = len(rows)
    zero = sum(v[1] for v in per.values())
    ranked = sorted(((k, v[0], v[1]) for k, v in per.items()), key=lambda x: -x[1])[:top_n or 0]
    return {
        "total": total,
        "zero": zero,
        "ratio": zero / total if total else 0.0,
        "by_company": [{"company": k, "jobs": t, "zero": z,
                        "zero_ratio": (z / t if t else 0.0)} for k, t, z in ranked],
    }


def must_stats(rows, demand) -> dict:
    """硬性要求占比（与 README / PROJECT_REPORT 同口径：占全语料岗位数）。

    `evidence` 记录 must 判定的来源分布（句内触发词 / 章节归属 / 占比兜底），
    现有语料应复现「56.5% / 1.49 项每岗 / 句内 4830 · 章节 175 · 兜底 1804」。
    """
    total = len(rows)
    judged_jobs = with_must = must_items = 0
    evidence: Counter = Counter()
    for r in rows:
        if not r["skill_spans"]:
            continue
        judged_jobs += 1
        judged = judge_requirements(r["text"], r["skill_spans"], demand=demand)
        musts = [info for info in judged.values() if info["is_must"]]
        if musts:
            with_must += 1
        must_items += len(musts)
        for info in musts:
            text = info["evidence"]
            kind = "句内" if text.startswith("句内含") else ("章节" if text.startswith("位于") else "兜底")
            evidence[kind] += 1
    return {
        "total_rows": total,
        "jobs_with_skills": judged_jobs,
        "jobs_with_must": with_must,
        "must_ratio": (with_must / total) if total else 0.0,
        "must_ratio_with_skills": (with_must / judged_jobs) if judged_jobs else 0.0,
        "must_per_job": (must_items / total) if total else 0.0,
        "evidence": dict(evidence),
    }



def predict_merge(existing_rows, new_rows, rule, tax) -> dict:
    """模拟 `build_dataset` 的去重后合并（新源追加在末尾），给出关键指标的预测值。"""
    existing_hash = {r["text_hash"] for r in existing_rows}
    kept_new = [r for r in new_rows if r["text_hash"] not in existing_hash]
    merged = list(existing_rows) + kept_new
    extract_rows(merged, rule)
    demand = compute_demand(merged)
    coverage = len({sid for r in merged for sid in r["skills"]})
    return {
        "jobs_before": len(existing_rows),
        "jobs_after": len(merged),
        "kept_new": len(kept_new),
        "dropped_new": len(new_rows) - len(kept_new),
        "companies_after": len({r["company"] for r in merged if r["company"]}),
        "zero": zero_skill_stats(merged, top_n=0),
        "skill_coverage": coverage,
        "skills_total": len(tax.all_skills()),
        "must": must_stats(merged, demand),
    }


def check_skills_column(paths, tax) -> dict | None:
    """若新 CSV 自带 skills 列（HF / Kaggle 数据集常见），直接比对词表覆盖找缺口技能。"""
    total = resolved = files_found = 0
    missing: Counter = Counter()
    for path in paths:
        try:
            df = pd.read_csv(path, dtype=str, keep_default_na=False)
        except (OSError, ValueError, pd.errors.ParserError):
            continue
        col = next((c for c in df.columns
                    if str(c).strip().lower() in _SKILLS_COLUMNS), None)
        if col is None:
            continue
        files_found += 1
        for raw in df[col]:
            for token in _SKILL_SPLIT_RE.split(str(raw or "")):
                token = token.strip()
                if not token:
                    continue
                total += 1
                if tax.resolve(token):
                    resolved += 1
                else:
                    missing[token.lower()] += 1
    if not files_found:
        return None
    return {
        "files": files_found,
        "tokens": total,
        "resolved": resolved,
        "coverage": (resolved / total) if total else 0.0,
        "missing_top": missing.most_common(15),
    }


def _fmt_top(items, limit: int = 6) -> str:
    return "、".join(f"{name}×{cnt}" for name, cnt in items[:limit]) or "—"


def _ev(pred, kind: str) -> int:
    """must 判定的来源计数（句内 / 章节 / 兜底）。"""
    return int((pred.get("must") or {}).get("evidence", {}).get(kind, 0))



def render(report) -> str:
    """把报告渲染成可读文本（分节 + 结论清单 + 下一步命令）。"""
    p = report["params"]
    src, st = report["source"], report["source"]["stats"]
    base, pred, comp = report["existing"], report["prediction"], report["company"]
    ident, txt = report["identity"], report["text"]
    lines: list[str] = [
        "=== 新数据源接入体检（只读，不落库）===",
        f"数据源：{'、'.join(Path(f).name for f in src['files'])}",
        f"参数：min_jd_chars={p['min_jd_chars']} / 零技能区间 "
        f"{p['zero_skill_band'][0]:.0%}~{p['zero_skill_band'][1]:.0%}"
        f" / 技能覆盖下限 {p['min_skill_coverage']}",
        f"现有语料：{base['jobs']} 条 / {base['companies']} 家"
        f" / 零技能 {base['zero']['ratio']:.1%} / 技能覆盖 {base['skill_coverage']}",
        "",
        "[1] 结构",
        f"  原始 {st['raw_rows']} → 可用 {src['rows']} 行（空正文 {st['empty_text']}"
        f" / 过短 {st['dropped_short']} / 标题过滤 {st['dropped_offtopic']}）",
        f"  公司 {src['companies']} 家（新增 {comp['added_company_count']}："
        f"{'、'.join(comp['added_companies']) or '—'}）",
        f"  技能 {src['skills']} 种；Top：{_fmt_top(src['top_skills'])}",
        "",
        "[2] job_id",
        f"  缺 id {ident['missing']} / 源内重复 {ident['dup_in_new_count']}"
        f" / 与现有语料冲突 {ident['collision_count']}"
        + (f"（{'、'.join(ident['collisions'])}）" if ident["collision_count"] else ""),
        "",
        "[3] 正文重复",
        f"  跨源 {txt['overlap_count']} 篇 / 源内 {txt['dup_in_new_rows']} 行；"
        f"新源在后丢 {txt['dropped_if_new_last']} 行、放最前覆盖旧行 {txt['dropped_if_new_first']} 行",
    ]
    if txt["overlap_samples"]:
        lines.append(f"  样例标题：{'、'.join(txt['overlap_samples'])}")
    lines += ["", "[4] 公司归一"]
    if comp["variants_cross_count"] or comp["variants_inner_count"]:
        for norm, group in list(comp["variants_cross"].items())[:3]:
            lines.append(f"  跨源：{norm} ← 现有 {'/'.join(group['existing'])}"
                         f" vs 新增 {'/'.join(group['new'])}")
        for norm, names in list(comp["variants_inner"].items())[:3]:
            lines.append(f"  源内：{norm} ← {'/'.join(names)}")
        lines.append("  → 归一函数不做别名合并：合并前先统一公司写法，否则公司数虚高")
    else:
        lines.append("  无「同归一多写法」")
    lines += ["", "[5] 新源抽取（仅新数据）"]
    zero_new = src["zero"]
    lines.append(f"  零技能 {zero_new['zero']}/{zero_new['total']} ({zero_new['ratio']:.1%})")
    for row in zero_new["by_company"][:5]:
        lines.append(f"    {row['company']}：{row['zero']}/{row['jobs']} ({row['zero_ratio']:.1%})")
    lines += ["", "[6] 合并预测（新源追加在末尾）",
              f"  行数 {pred['jobs_before']} → {pred['jobs_after']}"
              f"（新增 {pred['kept_new']}，重复丢弃 {pred['dropped_new']}）",
              f"  公司 {base['companies']} → {pred['companies_after']}",
              f"  零技能 {base['zero']['ratio']:.1%} → {pred['zero']['ratio']:.1%}"
              f"（{pred['zero']['zero']}/{pred['zero']['total']}）",
              f"  技能覆盖 {pred['skill_coverage']}/{pred['skills_total']}"
              f"（现有 {base['skill_coverage']}）",
              f"  硬性要求 {base['must']['must_ratio']:.1%} → {pred['must']['must_ratio']:.1%}"
              f"（{pred['must']['must_per_job']:.2f} 项/岗；句内 {_ev(pred, '句内')}"
              f" / 章节 {_ev(pred, '章节')} / 兜底 {_ev(pred, '兜底')}）"]
    sc = report.get("skills_column")
    if sc is not None:
        lines += ["", "[7] 自带 skills 列",
                  f"  {sc['resolved']}/{sc['tokens']} ({sc['coverage']:.1%}) 可解析"]
        if sc["missing_top"]:
            lines.append(f"  未覆盖 Top：{'、'.join(f'{t}×{c}' for t, c in sc['missing_top'][:8])}")
    lines += ["", "=== 结论 ==="]
    for chk in report["checks"]:
        icon = _STATUS_ICON.get(chk["status"], "•")
        lines.append(f"  {icon} {chk['status']:<4} {chk['name']}：{chk['detail']}")
    if exit_code(report["checks"]):
        lines += ["", "→ 存在 FAIL：先修数据/列映射，不要带着 FAIL 跑 merge_jobs.py。"]
    else:
        lines += ["", "→ 无 FAIL：可以合并构建；构建后按 memory-bank/dataOnboarding.md 同步常量与文档：",
                  "   1) python scripts/merge_jobs.py && python -m src.data.build_dataset --stats",
                  "   2) python scripts/recalc_importance.py（技能占比有变化时）",
                  "   3) python scripts/eval_all.py（更新 docs/metrics.md）",
                  "   4) 改 tests/test_dataset_snapshot.py 常量 + tests/test_skillkb.py importance 断言",
                  "   5) README / PROJECT_REPORT / memory-bank 数字同步 → 全量 pytest"]
    return "\n".join(lines)


def run(paths, *, jobs=DEFAULT_JOBS, config=DEFAULT_CONFIG, taxonomy=DEFAULT_TAXONOMY,
        min_jd_chars=None, zero_skill_band=ZERO_SKILL_BAND,
        min_skill_coverage=MIN_SKILL_COVERAGE) -> dict:
    """跑完全部体检，返回可 JSON 序列化的报告（只读现有语料与新 CSV）。"""
    mapping, cfg = load_config(config)
    cleaning = cfg.get("cleaning") or {}
    title_cfg = cleaning.get("title_filter") or {}
    min_chars = int(min_jd_chars if min_jd_chars is not None
                    else cleaning.get("min_jd_chars", 30))
    tax = Taxonomy(str(taxonomy))
    rule = RuleBaselineExtractor(tax)

    existing = load_existing(jobs)
    extract_rows(existing, rule)

    source = load_source(
        paths, mapping, min_jd_chars=min_chars,
        title_filter=bool(title_cfg.get("enabled", True)),
        exclude_keywords=title_cfg.get("exclude_keywords") or None,
        keep_keywords=title_cfg.get("keep_keywords") or None,
    )
    new_rows = source["rows"]
    extract_rows(new_rows, rule)

    top = Counter(sid for r in new_rows for sid in set(r["skills"])).most_common(8)
    report = {
        "params": {
            "min_jd_chars": min_chars,
            "zero_skill_band": list(zero_skill_band),
            "min_skill_coverage": int(min_skill_coverage),
            "must_tolerance": MUST_RATIO_TOLERANCE,
            "high_zero_skill_company": HIGH_ZERO_SKILL_COMPANY,
        },
        "source": {
            "files": source["stats"]["files"],
            "stats": source["stats"],
            "rows": len(new_rows),
            "companies": len({r["company"] for r in new_rows if r["company"]}),
            "skills": len({sid for r in new_rows for sid in r["skills"]}),
            "top_skills": [((tax.by_id(sid).name if tax.by_id(sid) else sid), c)
                           for sid, c in top],
            "zero": zero_skill_stats(new_rows, top_n=5),
        },
        "missing_required": sorted(source["stats"]["empty_required"]),
        "existing": {
            "jobs": len(existing),
            "companies": len({r["company"] for r in existing if r["company"]}),
            "zero": zero_skill_stats(existing, top_n=0),
            "skill_coverage": len({sid for r in existing for sid in r["skills"]}),
            "must": must_stats(existing, compute_demand(existing)),
        },
        "identity": check_identity(new_rows, existing),
        "text": check_text(new_rows, existing),
        "company": check_company(new_rows, existing),
        "prediction": predict_merge(existing, new_rows, rule, tax),
        "skills_column": check_skills_column(paths, tax),
    }
    report["checks"] = build_checks(report)
    return report


def _parse_band(text: str) -> tuple[float, float]:
    parts = [p.strip() for p in str(text).replace("~", ",").replace("，", ",").split(",")]
    if len(parts) != 2:
        raise ValueError("--zero-skill-band 需形如 0.20,0.28")
    return float(parts[0]), float(parts[1])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="新数据源接入前体检（只读）：合并前预演冲突、重复、零技能率与指标偏移")
    parser.add_argument("--source", nargs="+", required=True, help="新 CSV 路径（可多个）")
    parser.add_argument("--jobs", default=str(DEFAULT_JOBS), help="现有语料 jobs.jsonl")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG),
                        help="dataset.yaml（复用列映射与 min_jd_chars / 标题过滤）")
    parser.add_argument("--taxonomy", default=str(DEFAULT_TAXONOMY), help="技能词表 yaml")
    parser.add_argument("--min-jd-chars", type=int, default=None, help="覆盖 config 的最短正文长度")
    parser.add_argument("--zero-skill-band", default="0.20,0.28",
                        help="合并后零技能占比允许区间，默认与 slow 用例一致")
    parser.add_argument("--min-skill-coverage", type=int, default=MIN_SKILL_COVERAGE,
                        help="合并后技能覆盖下限（技能种类数）")
    parser.add_argument("--json", default=None, help="把完整报告另存为 JSON")
    args = parser.parse_args(argv)

    try:
        band = _parse_band(args.zero_skill_band)
    except ValueError as exc:
        parser.error(str(exc))

    report = run(args.source, jobs=args.jobs, config=args.config, taxonomy=args.taxonomy,
                 min_jd_chars=args.min_jd_chars, zero_skill_band=band,
                 min_skill_coverage=args.min_skill_coverage)
    _utf8_stdout()
    print(render(report))
    if args.json:
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
        print(f"\nJSON 报告：{args.json}")
    return exit_code(report["checks"])


if __name__ == "__main__":
    raise SystemExit(main())




_STATUS_ICON = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}


def build_checks(report) -> list[dict]:
    """把体检结果翻译成 PASS / WARN / FAIL 清单（FAIL 必须处理后再合并）。"""
    p = report["params"]
    checks: list[dict] = []

    def add(name: str, status: str, detail: str) -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    src, st = report["source"], report["source"]["stats"]
    if report["missing_required"]:
        add("必需列", "FAIL", f"整列为空（列映射不对？）：{'、'.join(report['missing_required'])}")
    if not src["rows"]:
        add("可用行", "FAIL", "清洗后 0 行：全部空正文 / 过短 / 被标题过滤")
    else:
        add("可用行", "PASS",
            f"原始 {st['raw_rows']} 行 → 可用 {src['rows']} 行"
            f"（空正文 {st['empty_text']} / 过短 {st['dropped_short']} / 标题过滤 {st['dropped_offtopic']}）")

    ident = report["identity"]
    if ident["collision_count"]:
        add("job_id 冲突", "FAIL",
            f"{ident['collision_count']} 个 job_id 与现有语料重复"
            f"（merge_jobs keep=first 会静默丢行）：{'、'.join(ident['collisions'])}")
    elif ident["dup_in_new_count"]:
        add("job_id 冲突", "FAIL",
            f"源内重复 {ident['dup_in_new_count']} 个：{'、'.join(ident['dup_in_new'])}")
    elif ident["missing"]:
        add("job_id", "WARN", f"{ident['missing']} 行缺 job_id（构建时自动编号，重建会漂移）")
    else:
        add("job_id", "PASS", "无冲突、无重复")

    txt = report["text"]
    if txt["overlap_count"] or txt["dup_in_new_count"]:
        add("正文重复", "WARN",
            f"与现有语料重复 {txt['overlap_count']} 篇"
            f"（新源在后丢 {txt['dropped_if_new_last']} 行；放最前会覆盖旧行 "
            f"{txt['dropped_if_new_first']} 行）/ 源内重复 {txt['dup_in_new_rows']} 行")
    else:
        add("正文重复", "PASS", "无跨源 / 源内重复")

    comp = report["company"]
    if comp["variants_cross_count"] or comp["variants_inner_count"]:
        add("公司写法分裂", "WARN",
            f"跨源同归一多写法 {comp['variants_cross_count']} 组 / "
            f"源内多写法 {comp['variants_inner_count']} 组 —— 会被统计成不同公司")
    else:
        add("公司归一", "PASS", f"新增 {comp['added_company_count']} 家，无写法分裂")

    zero_new = src["zero"]
    if zero_new["ratio"] > p["high_zero_skill_company"]:
        add("新源零技能率", "WARN",
            f"{zero_new['zero']}/{zero_new['total']} ({zero_new['ratio']:.1%})"
            f" 超过 {p['high_zero_skill_company']:.0%}（多为整站列表式短 JD，兜底负担变重）")
    else:
        add("新源零技能率", "PASS", f"{zero_new['zero']}/{zero_new['total']} ({zero_new['ratio']:.1%})")

    pred = report["prediction"]
    lo, hi = p["zero_skill_band"]
    ratio = pred["zero"]["ratio"]
    detail = f"{pred['zero']['zero']}/{pred['zero']['total']} ({ratio:.1%})"
    if lo <= ratio <= hi:
        add("合并后零技能占比", "PASS", f"{detail} 在 {lo:.0%}~{hi:.0%} 内")
    else:
        add("合并后零技能占比", "FAIL", f"{detail} 超出 {lo:.0%}~{hi:.0%}")

    cov = pred["skill_coverage"]
    if cov >= p["min_skill_coverage"]:
        add("合并后技能覆盖", "PASS", f"{cov}/{pred['skills_total']} ≥ {p['min_skill_coverage']}")
    else:
        add("合并后技能覆盖", "FAIL", f"{cov}/{pred['skills_total']} < {p['min_skill_coverage']}")

    base = report["existing"]["must"]["must_ratio"]
    delta = (pred["must"]["must_ratio"] - base) * 100
    tol = p["must_tolerance"] * 100
    detail = (f"{base:.1%} → {pred['must']['must_ratio']:.1%}"
              f"（{delta:+.1f}pt，容差 ±{tol:.0f}pt；{pred['must']['must_per_job']:.2f} 项/岗）")
    add("硬性要求占比", "PASS" if abs(delta) <= tol else "WARN", detail)

    sc = report.get("skills_column")
    if sc is not None:
        gaps = [(t, c) for t, c in sc["missing_top"] if c >= 2]
        if gaps:
            add("自带 skills 列覆盖", "WARN",
                f"{sc['resolved']}/{sc['tokens']} 可解析；词表未覆盖 "
                f"{'、'.join(f'{t}×{c}' for t, c in gaps[:5])}（考虑补进 skill_taxonomy.yaml）")
        else:
            add("自带 skills 列覆盖", "PASS", f"{sc['resolved']}/{sc['tokens']} ({sc['coverage']:.1%}) 可解析")
    return checks


def exit_code(checks) -> int:
    """有 FAIL 即返回 1（可接在 CI / 脚本链里当闸门）。"""
    return 1 if any(c["status"] == "FAIL" for c in checks) else 0



