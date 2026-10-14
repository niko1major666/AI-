"""英文岗位标题 -> 中文翻译（词典 + 词级启发式，无外部 API）。"""
from __future__ import annotations

_TITLE_DICT = {
    "AI Engineer": "AI工程师",
    "AI System Engineer": "AI系统工程师",
    "ML/AI Engineer": "机器学习/AI工程师",
    "ML Engineer": "机器学习工程师",
    "Machine Learning Engineer": "机器学习工程师",
    "Deep Learning Engineer": "深度学习工程师",
    "Data Scientist": "数据科学家",
    "Data Engineer": "数据工程师",
    "Data Analyst": "数据分析师",
    "Software Engineer": "软件工程师",
    "Computer Vision Engineer": "计算机视觉工程师",
    "NLP Engineer": "NLP工程师",
    "Research Scientist": "研究科学家",
    "Research Engineer": "研究工程师",
    "Applied Scientist": "应用科学家",
    "Product Manager": "产品经理",
    "Full Stack Engineer": "全栈工程师",
    "Backend Engineer": "后端工程师",
    "Frontend Engineer": "前端工程师",
    "DevOps Engineer": "DevOps工程师",
    "MLOps Engineer": "MLOps工程师",
    "Infrastructure Engineer": "基础设施工程师",
    "Platform Engineer": "平台工程师",
    "Algorithm Engineer": "算法工程师",
    "Systems Engineer": "系统工程师",
    "Prompt Engineer": "提示词工程师",
    "AI Operations Lead": "AI运营负责人",
    "AI Architect": "AI架构师",
    "AI Product Manager": "AI产品经理",
}

_WORD_DICT = {
    "Machine Learning": "机器学习",
    "Deep Learning": "深度学习",
    "Computer Vision": "计算机视觉",
    "Data Science": "数据科学",
    "Data Engineering": "数据工程",
    "Software Engineering": "软件工程",
    "Full Stack": "全栈",
    "Engineer": "工程师",
    "Scientist": "科学家",
    "Developer": "开发工程师",
    "Architect": "架构师",
    "Manager": "经理",
    "Analyst": "分析师",
    "Software": "软件",
    "Algorithm": "算法",
    "Research": "研究",
    "Backend": "后端",
    "Frontend": "前端",
    "Infrastructure": "基础设施",
    "Platform": "平台",
    "Product": "产品",
    "Lead": "负责人",
    "Senior": "高级",
    "Principal": "首席",
    "Staff": "资深",
    "Intern": "实习生",
    "Engineer, ": "工程师, ",
}


def translate_title(title: str) -> str:
    """把英文岗位标题翻译成中文；中文原样返回。"""
    if not title:
        return title
    t = str(title).strip()
    if any("\u4e00" <= c <= "\u9fff" for c in t):
        return t
    if t in _TITLE_DICT:
        return _TITLE_DICT[t]
    result = t
    for en, zh in _WORD_DICT.items():
        result = result.replace(en, zh)
    return result if result != t else t
