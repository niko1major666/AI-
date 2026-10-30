"""来源健康报告：按 source 汇总规模、新鲜度、发布时间覆盖与零技能率。

纯函数负责计算，`scripts/source_health.py` 负责读语料/跑抽取并落盘 Markdown。
报告不写入“当前时间”，而以语料里最新的 `last_seen_at` 作为基准（`as_of`），
这样 CI 重跑时不会因为日期变化产生无意义 diff。
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable, Optional

from .freshness import parse_time

SOURCE_LABELS = {
    "tech_kaggle": "英文科技岗（Kaggle）",
    "tencent": "腾讯",
    "bytedance": "字节跳动",
    "huawei": "华为",
    "xiaomi": "小米社招",
    "xiaomi_campus": "小米校招",
    "deepseek": "DeepSeek",
    "kimi": "Kimi",
    "minimax": "MiniMax",
    "kuaishou": "快手",
    "xiaohongshu": "小红书",
    "bilibili": "哔哩哔哩",
    "didi": "滴滴",
    "meituan": "美团",
    "local_csv": "本地 CSV",
}

STATUS_LABELS = {"ok": "✅ 正常", "warn": "⚠️ 关注", "fail": "❌ 异常"}


def source_label(source: str) -> str:
    return SOURCE_LABELS.get(str(source or ""), str(source or "未知"))


def _pct(part: int, total: int) -> float:
    return round(part / total, 4) if total else 0.0


def _age_days(then: Optional[datetime], now: datetime) -> Optional[int]:
    if then is None:
        return None
    return max(0, int((now - then).total_seconds() // 86400))


def build_report(jobs: Iterable[dict], *, state: Optional[dict] = None,
                 zero_skill_ids: Optional[set] = None,
                 as_of=None, stale_days: int = 30) -> dict:
    """生成来源健康数据。

    - zero_skill_ids：可选，零技能岗位的 job_id 集合；不传时报告不计算零技能率。
    - state：freshness 状态文件；用于统计“往期出现过、本轮未出现”的已消失岗位。
    - as_of：基准时间；缺省取语料中最大的 last_seen_at，保证报告可复现。
    """
    rows = [dict(r) for r in jobs]
    as_of_dt = parse_time(as_of)
    if as_of_dt is None:
        seen = [parse_time(r.get("last_seen_at")) for r in rows]
        as_of_dt = max((x for x in seen if x is not None), default=None)
    as_of_dt = as_of_dt or datetime.now(timezone.utc)

    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[str(r.get("source") or "")].append(r)

    inactive_by_source: dict[str, int] = defaultdict(int)
    for entry in ((state or {}).get("jobs") or {}).values():
        if isinstance(entry, dict) and not entry.get("active", True):
            inactive_by_source[str(entry.get("source") or "")] += 1

    sources = []
    for source, group in groups.items():
        total = len(group)
        last_times = [parse_time(r.get("last_seen_at")) for r in group]
        last_times = [x for x in last_times if x is not None]
        last_seen = max(last_times) if last_times else None
        age = _age_days(last_seen, as_of_dt)
        stale = sum(1 for x in last_times if _age_days(x, as_of_dt) > stale_days)
        publish_ok = sum(1 for r in group if str(r.get("publish_time") or "").strip())
        zero = (sum(1 for r in group if str(r.get("job_id") or "") in zero_skill_ids)
                if zero_skill_ids is not None else None)
        zero_ratio = _pct(zero, total) if zero is not None else None

        status = "ok"
        if zero_ratio is not None and total >= 20:
            if zero_ratio >= 0.50:
                status = "fail"
            elif zero_ratio >= 0.35:
                status = "warn"
        if status == "ok" and _pct(stale, total) >= 0.50:
            status = "warn"
        if status == "ok" and _pct(publish_ok, total) < 0.30:
            status = "warn"

        sources.append({
            "source": source,
            "label": source_label(source),
            "jobs": total,
            "companies": len({str(r.get("company") or "") for r in group}),
            "last_seen_at": last_seen.isoformat() if last_seen else "",
            "age_days": age,
            "stale_jobs": stale,
            "stale_ratio": _pct(stale, total),
            "publish_time_jobs": publish_ok,
            "publish_time_coverage": _pct(publish_ok, total),
            "zero_skill_jobs": zero,
            "zero_skill_ratio": zero_ratio,
            "inactive_jobs": inactive_by_source.get(source, 0),
            "status": status,
        })

    sources.sort(key=lambda x: (-x["jobs"], x["label"]))

    total_jobs = len(rows)
    total_stale = sum(s["stale_jobs"] for s in sources)
    total_publish = sum(s["publish_time_jobs"] for s in sources)
    total_zero = (sum(s["zero_skill_jobs"] or 0 for s in sources)
                  if zero_skill_ids is not None else None)
    seen_all = [parse_time(r.get("last_seen_at")) for r in rows]
    latest = max((x for x in seen_all if x is not None), default=None)
    totals = {
        "jobs": total_jobs,
        "companies": len({str(r.get("company") or "") for r in rows}),
        "sources": len(sources),
        "stale_jobs": total_stale,
        "stale_ratio": _pct(total_stale, total_jobs),
        "publish_time_jobs": total_publish,
        "publish_time_coverage": _pct(total_publish, total_jobs),
        "zero_skill_jobs": total_zero,
        "zero_skill_ratio": _pct(total_zero, total_jobs) if total_zero is not None else None,
        "inactive_history_jobs": sum(inactive_by_source.values()),
        "latest_seen_at": latest.isoformat() if latest else "",
    }
    return {
        "as_of": as_of_dt.isoformat(),
        "stale_days": stale_days,
        "totals": totals,
        "sources": sources,
    }



def _fmt_pct(value) -> str:
    return "-" if value is None else f"{value:.1%}"


def _fmt_age(days) -> str:
    if days is None:
        return "-"
    return "今天" if days <= 0 else f"{days} 天"


def render_markdown(report: dict) -> str:
    """渲染为稳定、可 diff 的 Markdown 报告。"""
    t = report["totals"]
    lines = [
        "# 数据源健康（自动生成）",
        "",
        "> 由 `python scripts/source_health.py` 生成；改动词表 / 数据源 / 构建逻辑后请重跑并提交。",
        f"> 基准时间：`{report['as_of']}`（语料中最新的抓取时间）；"
        f"超过 **{report['stale_days']} 天**未再抓到视为“可能已下线”。",
        "> `last_seen_at` 来自各源 CSV 落盘时间，构建本身不会刷新它；"
        "`first_seen_at` 由 `data/processed/job_freshness.json` 跨构建保留。",
        "",
        "## 总览",
        "",
        f"- 在架岗位：**{t['jobs']}** 条 / **{t['companies']}** 家公司 / **{t['sources']}** 个来源",
        f"- 发布时间字段覆盖：**{t['publish_time_jobs']}** 条（{_fmt_pct(t['publish_time_coverage'])}）",
        f"- 超过 {report['stale_days']} 天未更新：**{t['stale_jobs']}** 条（{_fmt_pct(t['stale_ratio'])}）",
        f"- 往期出现过、本轮未出现：**{t['inactive_history_jobs']}** 条（保留在新鲜度状态文件中）",
    ]
    if t.get("zero_skill_jobs") is not None:
        lines.append(f"- 零技能岗位：**{t['zero_skill_jobs']}** 条"
                     f"（{_fmt_pct(t['zero_skill_ratio'])}，由规则抽取器统计）")
    lines += [
        "",
        "## 分来源",
        "",
        "| 来源 | 岗位 | 公司 | 最新抓取 | 距今 | 发布覆盖 | 零技能 | 可能下线 | 已消失 | 状态 |",
        "|---|---:|---:|---|---:|---:|---:|---:|---:|---|",
    ]
    for s in report["sources"]:
        zero = (f"{s['zero_skill_jobs']}（{_fmt_pct(s['zero_skill_ratio'])}）"
                if s.get("zero_skill_jobs") is not None else "-")
        lines.append(
            f"| {s['label']} (`{s['source']}`) | {s['jobs']} | {s['companies']} | "
            f"{s['last_seen_at'][:10] or '-'} | {_fmt_age(s['age_days'])} | "
            f"{_fmt_pct(s['publish_time_coverage'])} | {zero} | {s['stale_jobs']} | "
            f"{s['inactive_jobs']} | {STATUS_LABELS.get(s['status'], s['status'])} |"
        )
    lines += [
        "",
        "## 判定口径",
        "",
        "- 零技能率 ≥ 50%（岗位数 ≥ 20）→ 异常；≥ 35% → 关注（差距报告会用同公司相似岗位兜底）。",
        f"- 超过 {report['stale_days']} 天未更新占比 ≥ 50% → 关注；发布时间覆盖 < 30% → 关注。",
        "- “已消失”依赖状态文件：只有跑过多次构建后才会累积，首次启用时为 0。",
        "",
    ]
    return "\n".join(lines)
