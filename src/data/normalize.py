"""文本清洗 / 公司归一 / 薪资解析 / 去重哈希（纯函数，无重依赖，可独立测试）。"""
from __future__ import annotations

import hashlib
import re

_HTML_RE = re.compile(r"<[^>]+>")
_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_WS_RE = re.compile(r"[ \t\u3000]+")

_COMPANY_SUFFIXES = [
    "股份有限公司", "有限责任公司", "有限公司", "集团公司", "集团", "公司",
    "limited", "company", "corporation", "corp.", "corp", "incorporated",
    "inc.", "inc", "ltd.", "ltd", "llc", "plc",
]

_SALARY_NEG = {"面议", "薪资面议", "薪资面谈", "open", "薪资open"}


def clean_text(s) -> str:
    """去 HTML 标签 / URL，压缩空白，归一换行。"""
    if not s:
        return ""
    t = str(s)
    t = _HTML_RE.sub(" ", t)
    t = _URL_RE.sub(" ", t)
    t = t.replace("\r", " ").replace("\n", " ")
    t = _WS_RE.sub(" ", t)
    return t.strip()


def normalize_company(s) -> str:
    """公司名归一：去括号、去法律形式后缀、小写。"""
    t = clean_text(s).lower()
    t = re.sub(r"[（(].*?[)）]", "", t)
    t = re.sub(r"\s+", "", t)
    for _ in range(6):
        stripped = False
        for sfx in _COMPANY_SUFFIXES:
            if t.endswith(sfx):
                t = t[: -len(sfx)]
                stripped = True
                break
        if not stripped:
            break
    return t.strip()


def sha1_text(s) -> str:
    """生成稳定去重哈希。"""
    return hashlib.sha1(str(s).encode("utf-8")).hexdigest()[:12]


def parse_salary(s):
    """解析薪资字符串 -> (min_k, max_k, months)，单位统一为「千元/月」。

    支持："30-60K·15薪"、"25-50K"、"年薪30-50万"、"3-5万·13薪"、
    "20000-40000元/月"、"面议"。无法解析返回 (None, None, None)。
    """
    t = (str(s) or "").strip()
    if not t or t in _SALARY_NEG:
        return (None, None, None)

    months = None
    m = re.search(r"(\d{1,2})\s*薪", t)
    if m:
        months = int(m.group(1))

    annual = bool(re.search(r"年薪|/年|每年|年收入", t))
    unit_wan = "万" in t
    unit_k = bool(re.search(r"[kK千]", t))

    # 先剔除干扰片段，再提取所有数字
    t2 = re.sub(r"\d{1,2}\s*薪", " ", t)
    t2 = re.sub(r"年薪|/年|每年|年收入|·|～|~|—|至|到", " ", t2)
    nums = re.findall(r"\d+(?:\.\d+)?", t2)
    if not nums:
        return (None, None, months)

    vals = []
    for n in nums:
        v = float(n)
        if unit_wan:
            v = v * 10000.0 / 1000.0          # 万 -> 千
        if ("元" in t) and not unit_k and not unit_wan:
            v = v / 1000.0                    # 元 -> 千
        if annual:
            v = v / 12.0                      # 年 -> 月
        vals.append(round(v, 1))
    return (min(vals), max(vals), months)
