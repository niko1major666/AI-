"""岗位「技术 / 非技术」判定（确定性规则，只看标题）。

**为什么需要**：企业招聘站同时挂技术岗与职能岗（运营/产品/销售/财务/税务/合规）。
职能岗抽不到技术技能是**正确行为**，但会让「零技能率」这个指标长期偏高、
看起来像抽取器坏了。v1.7.1 的归因（`docs/source-triage-v1.7.md` §3）实测：

| 源 | 零技能 | 其中非技术岗 |
|---|---|---|
| 快手 | 454（32.5%） | 361（79.5%） |
| 小红书 | 480（37.4%） | 363（75.6%） |

因此把「技术岗零技能率」单独算出来，让指标可行动；**不改判定阈值、不改词表**。

规则顺序（技术标记优先，避免「产品研发工程师」被误判为职能岗）：

1. 标题含技术标记 → `tech`
2. 否则标题含职能词 → `non_tech`
3. 都没有 → `unknown`（不计入技术岗分母）
"""
from __future__ import annotations

TECH_MARKERS = (
    "工程师", "开发", "算法", "后端", "前端", "服务端", "客户端", "全栈", "架构",
    "测试", "运维", "技术", "研发", "安全", "机器学习", "深度学习", "数据",
    "nlp", "cv", "infra", "sre", "dba", "大数据", "嵌入式", "硬件", "芯片",
    "android", "ios", "java", "python", "golang", "c++", "php", "ruby", "rust",
)

NON_TECH_MARKERS = (
    "运营", "产品", "设计", "销售", "市场", "品牌", "人力资源", "hr", "招聘",
    "财务", "会计", "税务", "法务", "合规", "审计", "风控", "内控", "行政",
    "客服", "供应链", "采购", "物流", "仓储", "商务", "渠道", "公关", "编辑",
    "内容", "策划", "培训", "战略", "投资", "商业化", "达人", "直播", "电商",
    "bd", "bp", "助理", "实习生",
)


def classify_title(title) -> str:
    """返回 `tech` / `non_tech` / `unknown`。"""
    text = str(title or "").lower()
    if not text:
        return "unknown"
    if any(marker in text for marker in TECH_MARKERS):
        return "tech"
    if any(marker in text for marker in NON_TECH_MARKERS):
        return "non_tech"
    return "unknown"


def is_tech_title(title) -> bool:
    """标题是否属于技术岗（供零技能率分层统计）。"""
    return classify_title(title) == "tech"
