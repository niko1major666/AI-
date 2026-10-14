"""爬虫通用工具。"""
from __future__ import annotations


def fmt_publish_time(pt):
    """把发布时间各种格式统一成 'YYYY-MM-DD' 或原字符串。"""
    if pt is None or pt == "":
        return ""
    try:
        n = int(pt)
        if n > 1e12:  # 毫秒时间戳
            n = n / 1000
        from datetime import datetime
        return datetime.fromtimestamp(n).strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001
        return str(pt)[:10]
