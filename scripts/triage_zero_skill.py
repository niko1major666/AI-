"""零技能岗位归因：把「零技能」拆成可行动的三类，供 triage 决策使用。

背景：`docs/source_health.md` 里快手 32.5% / 小红书 37.4% 零技能率被列为「关注」，
但「零技能」本身不是缺陷——企业官网里有大量非技术岗（运营/产品/销售/财务），
它们当然抽不到技术技能。直接调阈值或硬扩词表都是错的，先用本脚本归因。

分类规则（全部基于标题与 JD 的确定性判断，不调模型）：

1. `nonTech`：标题命中职能词（运营/产品/设计/销售/税务/合规…）且不含技术标记
2. `suspectedVocabGap`：标题没被判为非技术岗，但 JD 里出现英文技能样 token（ios/sql/kubernetes…）
   ——这批最可能是词表/别名缺口，但需要人工确认（`roi`/`gmv` 这类业务缩写会混进来）
3. `manual`：其余，需人工看样例

口径与 `scripts/source_health.py` 完全一致（直接复用 `zero_skill_job_ids`），
所以这里的 `zeroSkill` 数与报告里的数字必然相等。

用法：

    python scripts/triage_zero_skill.py --sources kuaishou,xiaohongshu
    python scripts/triage_zero_skill.py --sources kuaishou --samples 5
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

NON_TECH = (
    "运营", "产品", "设计", "销售", "市场", "品牌", "人力资源", "hr", "招聘", "财务",
    "会计", "税务", "法务", "合规", "审计", "风控", "内控", "行政", "客服", "供应链",
    "采购", "物流", "仓储", "商务", "渠道", "公关", "编辑", "内容", "策划", "培训",
    "战略", "投资", "商业化", "达人", "直播", "电商", "bd", "bp",
)
# 出现这些词就视为技术岗，即使标题里含「产品/设计」等词（如「产品研发工程师」）
TECH_MARK = (
    "工程师", "开发", "算法", "后端", "前端", "架构", "测试", "运维", "技术", "研发",
    "sre", "dba", "机器学习", "深度学习", "nlp", "cv", "infra", "数据", "安全",
)
LATIN_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9+#._-]{2,}")
STOP = {
    "the", "and", "for", "with", "you", "our", "are", "will", "team", "work", "job",
    "company", "description", "requirements", "responsibilities", "ability", "good",
    "experience", "years", "plus", "etc", "all", "new", "use", "using", "have",
}
DEFAULT_JOBS = ROOT / "data" / "processed" / "jobs.jsonl"


def classify(jobs: list[dict], zero_ids: set, source: str, samples: int) -> dict:
    rows = [j for j in jobs if str(j.get("source")) == source]
    zero_rows = [j for j in rows if str(j.get("job_id")) in zero_ids]

    non_tech: list[dict] = []
    vocab_gap: list[dict] = []
    manual: list[dict] = []
    tokens: Counter = Counter()
    tech_marked = 0

    for job in zero_rows:
        title = str(job.get("title") or "").lower()
        jd = str(job.get("jd_clean") or job.get("jd_text") or "")
        found = {m.group(0).lower() for m in LATIN_TOKEN.finditer(jd)} - STOP
        is_tech = any(mark in title for mark in TECH_MARK)
        if is_tech:
            tech_marked += 1
        if any(word in title for word in NON_TECH) and not is_tech:
            non_tech.append(job)
        elif found:
            vocab_gap.append(job)
            tokens.update(found)
        else:
            manual.append(job)

    def pct(n: int) -> float:
        return round(n / len(zero_rows) * 100, 1) if zero_rows else 0.0

    return {
        "source": source,
        "jobs": len(rows),
        "zeroSkill": len(zero_rows),
        "zeroSkillPct": round(len(zero_rows) / len(rows) * 100, 1) if rows else 0.0,
        "techMarkedZeroSkill": tech_marked,
        "buckets": {
            "nonTech": {"count": len(non_tech), "pct": pct(len(non_tech))},
            "suspectedVocabGap": {"count": len(vocab_gap), "pct": pct(len(vocab_gap))},
            "manual": {"count": len(manual), "pct": pct(len(manual))},
        },
        "topMissingTokens": [{"token": t, "count": c} for t, c in tokens.most_common(12)],
        "samples": {
            "nonTech": [str(j.get("title") or "")[:40] for j in non_tech[:samples]],
            "suspectedVocabGap": [
                {"title": str(j.get("title") or "")[:40], "jd": str(j.get("jd_clean") or "")[:120]}
                for j in vocab_gap[:samples]
            ],
            "manual": [str(j.get("title") or "")[:40] for j in manual[:samples]],
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="零技能岗位归因（nonTech / suspectedVocabGap / manual）")
    ap.add_argument("--jobs", default=str(DEFAULT_JOBS))
    ap.add_argument("--sources", default="kuaishou,xiaohongshu")
    ap.add_argument("--samples", type=int, default=3)
    args = ap.parse_args()

    from source_health import zero_skill_job_ids  # noqa: E402  同目录脚本

    jobs = [
        json.loads(line)
        for line in Path(args.jobs).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    zero_ids = zero_skill_job_ids(jobs)

    report = {
        "totalJobs": len(jobs),
        "zeroSkillJobs": len(zero_ids),
        "sources": [
            classify(jobs, zero_ids, src.strip(), args.samples)
            for src in args.sources.split(",")
            if src.strip()
        ],
    }
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
