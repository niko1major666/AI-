"""岗位标题过滤：剔除与 AI 岗位无关的工程类岗位，避免污染技能需求统计。

只作用于「标题」，不看 JD 正文：正文里的「桥梁」多为「业务与技术之间的桥梁」
一类比喻用法，据此删数据会误伤真实 AI 岗位（已用 25 条真实样本确认）。

判定顺序：先白名单（含 AI / 技术信号即保留）→ 再黑名单（命中工程类特征词即剔除）。
"""
from __future__ import annotations

import re

_SEP_RE = re.compile(r"[\s\-_/|·•（）()【】\[\]{}<>《》〈〉、,，.。:：;；!！?？'\"“”‘’]+")

# 黑名单：土建 / 施工 / 传统工程类岗位特征词
DEFAULT_EXCLUDE_KEYWORDS = (
    "土木", "土建", "建筑", "桥梁", "道桥", "桥隧", "隧道", "道路", "公路", "铁道",
    "岩土", "地质", "勘察", "测绘", "市政", "给排水", "暖通", "水利", "港航",
    "施工", "监理", "工程造价", "预算员", "预结算", "招投标", "施工图",
    "结构工程师", "机电工程", "消防工程", "工程测量", "园林", "景观", "城市规划",
)

# 白名单：命中任一即保留（AI / 技术信号），用于保护「建筑智能化 AI 产品经理」
# 「模型结构优化工程师」这类含工程词但确属 AI 的岗位
DEFAULT_KEEP_KEYWORDS = (
    "ai", "人工智能", "算法", "机器学习", "深度学习", "大模型", "llm", "aigc",
    "nlp", "cv", "视觉", "多模态", "语音", "agent", "机器人",
    "智能", "数据", "大数据", "模型", "推荐", "搜索",
    "python", "开发", "研发", "软件", "后端", "前端", "全栈", "测试", "运维", "架构", "平台",
)


def normalize_title(title) -> str:
    """标题归一：小写 + 去分隔符，避免「AI-建筑」「AI 建筑」匹配不一致。"""
    return _SEP_RE.sub("", str(title or "").lower())


_DEFAULT_KEEP = tuple(k for k in (normalize_title(w) for w in DEFAULT_KEEP_KEYWORDS) if k)
_DEFAULT_EXCLUDE = tuple(k for k in (normalize_title(w) for w in DEFAULT_EXCLUDE_KEYWORDS) if k)


def _prepare(words) -> tuple:
    return tuple(k for k in (normalize_title(w) for w in words) if k)


def is_offtopic_title(title, exclude_keywords=None, keep_keywords=None) -> bool:
    """标题是否属于与 AI 岗位无关的工程类岗位。

    exclude_keywords / keep_keywords 传 None 表示使用内置词表（传空列表则视为不启用该名单）。
    空标题不判为无关，交由其他清洗步骤处理。
    """
    t = normalize_title(title)
    if not t:
        return False
    keep = _DEFAULT_KEEP if keep_keywords is None else _prepare(keep_keywords)
    if any(k in t for k in keep):
        return False
    exclude = _DEFAULT_EXCLUDE if exclude_keywords is None else _prepare(exclude_keywords)
    return any(k in t for k in exclude)
