"""从 JD 文本本身判定技能的要求强度（must / nice），替代「全局需求占比」的伪判据。

背景（实测，5832 条语料）：没有任何技能的全局需求占比达到 40%（最高 38.6%，大模型），
原实现 `is_must = demand >= 0.4` 因此恒为 False —— 报告里 P0 分组永远为空、
`must_weight` 权重失效、why 文案从不出现「硬性要求」。实测：

技能判定的三级来源合计给出 60.0% 的岗位 / 1.80 个/岗
（有技能岗位 4580 条；句内 7340 / 章节 974 / 兜底 2191）。
采用三级判定：

1. 技能所在**句**内的语气触发词（加分语气优先：「熟悉 X 优先」里的「熟悉」不是硬门槛）；
2. 技能所在**段落**的章节标题（任职要求 → must；加分项 → nice）；
3. 兜底：全行业需求占比（默认 ≥ 30% 视为 must），对应数据驱动口径。
"""
from __future__ import annotations

import re

# 加分语气必须先判：中文「熟悉 X 优先」「精通 Y 加分」语句里也含 must 词，语义却是加分项
NICE_CUES = (
    "优先", "加分", "了解", "可选", "nice to have", "preferred", "a plus",
)
MUST_CUES = (
    "必须", "熟练掌握", "精通", "扎实", "硬性", "至少", "具备", "要求",
    "required", "requirements", "proficiency", "proficient", "strong experience",
)
MUST_SECTIONS = (
    "任职要求", "岗位要求", "职位要求", "任职资格", "任职条件", "你需要", "岗位职责", "工作职责",
    "requirements", "qualifications", "what you'll need",
)
NICE_SECTIONS = ("加分项", "优先条件", "加分条件", "nice to have", "bonus points")
STOP_SECTIONS = (
    "我们提供", "福利待遇", "薪资待遇", "简历投递", "关于我们", "工作地点",
    "about us", "benefits",
)

_SENT_RE = re.compile(r"[^。；;！!？?\n]+")


def _first_cue(low: str, cues) -> str:
    for cue in cues:
        if cue in low:
            return cue
    return ""


def _split_sentences(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in _SENT_RE.finditer(text)]


def _section_marks(text: str) -> list[tuple[int, str]]:
    """扫描每行行首，记录「章节标题」的起始偏移与类型（must / nice / stop）。"""
    marks: list[tuple[int, str]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        head = line.strip()[:24].lower()
        kind = ""
        if any(k in head for k in NICE_SECTIONS):
            kind = "nice"
        elif any(k in head for k in MUST_SECTIONS):
            kind = "must"
        elif any(k in head for k in STOP_SECTIONS):
            kind = "stop"
        if kind:
            marks.append((offset, kind))
        offset += len(line)
    return marks


def _section_at(marks: list[tuple[int, str]], pos: int) -> str:
    kind = ""
    for start, k in marks:
        if start > pos:
            break
        kind = k
    return kind


def judge_requirements(text: str, spans, demand: dict | None = None,
                       must_ratio: float = 0.3) -> dict[str, dict]:
    """判定每个技能是 must（硬性门槛）还是 nice（加分项）。

    spans: [(skill_id, start)]，或含 `.skill_id` / `.start` 属性的对象列表。
    demand: {skill_id: 全行业需求占比}，仅在第 1、2 级都无信号时兜底。
    返回 {skill_id: {"is_must": bool, "kind": "must"|"nice", "evidence": str}}。
    """
    text = text or ""
    demand = demand or {}
    sents = _split_sentences(text)
    marks = _section_marks(text)
    out: dict[str, dict] = {}

    for item in spans or []:
        sid, pos = item if isinstance(item, tuple) else (item.skill_id, item.start)
        if not sid:
            continue
        pos = int(pos or 0)
        sent = next((text[s:e] for s, e in sents if s <= pos < e), "")
        low = sent.lower()

        kind = evidence = ""
        cue = _first_cue(low, NICE_CUES)
        if cue:
            kind, evidence = "nice", f"句内含「{cue}」"
        else:
            cue = _first_cue(low, MUST_CUES)
            if cue:
                kind, evidence = "must", f"句内含「{cue}」"

        if not kind:
            section = _section_at(marks, pos)
            if section == "must":
                kind, evidence = "must", "位于「任职要求」段落"
            elif section == "nice":
                kind, evidence = "nice", "位于「加分项」段落"

        if not kind:
            ratio = float(demand.get(sid, 0.0) or 0.0)
            if ratio >= must_ratio:
                kind, evidence = "must", f"全行业需求占比 {ratio:.0%}"
            else:
                kind, evidence = "nice", ""

        prev = out.get(sid)
        # 同一技能在 JD 中出现多次：must 优先（取最强证据）
        if prev is None or (kind == "must" and not prev["is_must"]):
            out[sid] = {"is_must": kind == "must", "kind": kind, "evidence": evidence}
    return out


def must_skills(text: str, spans, demand: dict | None = None,
                must_ratio: float = 0.3) -> list[str]:
    """便捷封装：只返回硬性要求的 skill_id（保持确定性顺序）。"""
    judged = judge_requirements(text, spans, demand=demand, must_ratio=must_ratio)
    return sorted(sid for sid, info in judged.items() if info["is_must"])
