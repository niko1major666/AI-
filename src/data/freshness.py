"""岗位数据新鲜度：首次/最近抓取时间与在架状态（纯函数，可独立测试）。

设计约定
--------
- **last_seen_at**：该岗位最近一次出现在任一源 CSV 中的抓取时间；构建不会把它刷新成
  「本次构建时间」，否则所有岗位永远显示“今天更新”，失去新鲜度意义。
- **first_seen_at**：自本机制上线后，第一次在构建产物中观察到该 job_id 的时间；后续构建
  即使源文件更新，也保留最初值。
- **is_active**：当前构建产物中的岗位为 True；状态文件会保留往期 job_id，并把本轮未出现的
  标为 False（可用于来源健康里的“已消失岗位”统计）。jobs.jsonl 只输出本轮在架岗位。
- 状态按 job_id 保存，缺失/损坏时自动降级为空状态，不影响构建。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

DEFAULT_STALE_DAYS = 30
STATE_VERSION = 1


def parse_time(value) -> Optional[datetime]:
    """解析常见时间写法为 UTC aware datetime；无法解析返回 None。"""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        try:
            dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    else:
        s = str(value).strip()
        if not s:
            return None
        # ISO 8601（含 Z / 空格分隔 / 无时区）
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            dt = None
            for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S",
                        "%Y年%m月%d日", "%Y-%m-%dT%H:%M:%S"):
                try:
                    dt = datetime.strptime(s, fmt)
                    break
                except ValueError:
                    continue
            if dt is None:
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_iso(value) -> str:
    """统一序列化为 UTC ISO 字符串；无法解析时原样返回空串。"""
    dt = parse_time(value)
    return dt.isoformat() if dt else ""


def age_days(value, now=None) -> Optional[int]:
    """距今天数（向下取整，未来时间按 0 算）；无法解析返回 None。"""
    dt = parse_time(value)
    if dt is None:
        return None
    now_dt = parse_time(now) or datetime.now(timezone.utc)
    seconds = (now_dt - dt).total_seconds()
    return max(0, int(seconds // 86400))


def freshness_label(value, now=None) -> str:
    """面向用户的新鲜度文案：今天更新 / 昨天更新 / N 天前更新。"""
    days = age_days(value, now=now)
    if days is None:
        return ""
    if days <= 0:
        return "今天更新"
    if days == 1:
        return "昨天更新"
    return f"{days} 天前更新"


def is_stale(value, max_age_days: int = DEFAULT_STALE_DAYS, now=None) -> bool:
    """超过 max_age_days 未再抓到 → 可能已下线。时间缺失时返回 False（不误报）。"""
    dt = parse_time(value)
    if dt is None:
        return False
    now_dt = parse_time(now) or datetime.now(timezone.utc)
    return (now_dt - dt).total_seconds() > max(0, int(max_age_days)) * 86400


def filter_by_age(rows, max_age_days, *, now=None, field: str = "last_seen_at",
                  keep_unknown: bool = True) -> list:
    """按时间字段筛选岗位；max_age_days 为 None/0 时原样返回。

    keep_unknown=True 时保留缺时间字段的旧数据，避免升级/旧语料下筛选后列表全空。
    """
    rows = list(rows)
    if not max_age_days:
        return rows
    out = []
    for row in rows:
        value = (row or {}).get(field) or ""
        if not value:
            if keep_unknown:
                out.append(row)
        elif not is_stale(value, max_age_days, now=now):
            out.append(row)
    return out


def empty_state() -> dict:
    return {"version": STATE_VERSION, "updated_at": "", "jobs": {}}


def load_state(path) -> dict:
    """读状态文件；不存在/损坏/结构不符时返回空状态（构建不应因状态丢失而失败）。"""
    p = Path(path)
    if not p.exists():
        return empty_state()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty_state()
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), dict):
        return empty_state()
    try:
        version = int(data.get("version") or STATE_VERSION)
    except (TypeError, ValueError):
        version = STATE_VERSION
    return {
        "version": version,
        "updated_at": str(data.get("updated_at") or ""),
        "jobs": data["jobs"],
    }


def save_state(path, state: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    # sort_keys 让状态文件 diff 稳定，避免每次构建因字典顺序产生噪声
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True),
                 encoding="utf-8")


def annotate_jobs(records: Iterable[dict], state: Optional[dict] = None,
                  observed_at=None) -> tuple[list[dict], dict]:
    """给构建记录补 first_seen_at / last_seen_at / is_active，并返回更新后的状态。

    - 记录自身的 crawl_time 是“源抓取时间”；缺失时退回 observed_at（构建时间）。
    - first_seen_at 一旦写入状态就保持不变；last_seen_at 取历史与本次的较大值，
      避免旧源文件被重新合并时把时间倒退。
    - 状态中本轮未出现的 job_id 标记 active=False，供健康报告统计“已消失岗位”。
    """
    now_iso = to_iso(observed_at) or datetime.now(timezone.utc).isoformat()
    prev = (state or {}).get("jobs")
    prev_jobs = dict(prev) if isinstance(prev, dict) else {}
    historical = {str(k): dict(v) if isinstance(v, dict) else {}
                  for k, v in prev_jobs.items()}
    for entry in historical.values():
        entry["active"] = False

    out: list[dict] = []
    for record in records:
        row = dict(record)
        job_id = str(row.get("job_id") or "")
        if not job_id:
            continue
        seen = parse_time(row.get("crawl_time")) or parse_time(now_iso)
        seen_iso = seen.isoformat() if seen else now_iso
        old = historical.get(job_id) or {}
        first = parse_time(old.get("first_seen_at")) or seen or parse_time(now_iso)
        old_last = parse_time(old.get("last_seen_at"))
        last = max(seen, old_last) if (seen and old_last) else (seen or old_last)

        row["first_seen_at"] = first.isoformat() if first else seen_iso
        row["last_seen_at"] = last.isoformat() if last else seen_iso
        row["is_active"] = True
        historical[job_id] = {
            "first_seen_at": row["first_seen_at"],
            "last_seen_at": row["last_seen_at"],
            "source": str(row.get("source") or ""),
            "active": True,
        }
        out.append(row)

    updated = {
        "version": STATE_VERSION,
        "updated_at": now_iso,
        "jobs": {k: historical[k] for k in sorted(historical)},
    }
    return out, updated
