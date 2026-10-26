"""规则版学习路径：不依赖 LLM，把缺失技能排成「阶段 + 先修顺序 + 学时」。

差距报告原先只有 DeepSeek 可用时才出学习计划（无 key 时 plan 为空）。
这里用纯规则补一份确定性计划：按 P0/P1/P2 分三阶段，阶段内按先修关系拓扑排序，
学时由技能难度估算，周数按每周可投入时数向上取整。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

# 难度 -> 预估学时（含练习/小项目）。1=最容易，5=最难。
HOURS_BY_DIFFICULTY = {1: 2, 2: 4, 3: 8, 4: 16, 5: 24}

# 技能先修关系（a: [b] 表示学 a 之前建议先学 b）。
# 只登记「学起来会卡住」的强依赖，不做全序；未登记的技能视为无先修。
SKILL_PREREQS: dict[str, list[str]] = {
    # 编程 / 数据
    "BIGDATA.PANDAS": ["PROG.PYTHON"],
    "BIGDATA.NUMPY": ["PROG.PYTHON"],
    "BIGDATA.SPARK": ["PROG.SQL", "PROG.PYTHON"],
    "BIGDATA.DW": ["PROG.SQL"],
    "BIGDATA.ETL": ["PROG.SQL"],
    "BIGDATA.DBT": ["PROG.SQL"],
    # 机器学习基础链路
    "ML.DL": ["ML.CORE"],
    "ML.NN": ["ML.DL"],
    "ML.CNN": ["ML.NN"],
    "ML.RNN": ["ML.NN"],
    "ML.LSTM": ["ML.RNN"],
    "ML.TRANSFORMER": ["ML.DL"],
    "ML.ATTENTION": ["ML.TRANSFORMER"],
    "ML.NLP": ["ML.TRANSFORMER"],
    "ML.CV": ["ML.CNN"],
    "ML.MULTIMODAL": ["ML.CV", "ML.NLP"],
    "ML.VLM": ["ML.CV", "ML.TRANSFORMER"],
    "ML.DIFFUSION": ["ML.DL"],
    "ML.COMPRESS": ["ML.DL"],
    "ML.QUANT": ["ML.COMPRESS"],
    "ML.FED": ["ML.DL"],
    "ML.RL": ["ML.DL"],
    "FRAMEWORK.PYTORCH": ["PROG.PYTHON", "ML.NN"],
    "FRAMEWORK.TENSORFLOW": ["PROG.PYTHON", "ML.NN"],
    "FRAMEWORK.SKLEARN": ["PROG.PYTHON", "ML.CORE"],
    # 大模型链路
    "AITECH.LLM": ["ML.TRANSFORMER"],
    "AITECH.PROMPT": ["AITECH.LLM"],
    "AITECH.EMBEDDING": ["ML.DL"],
    "AITECH.RAG": ["AITECH.LLM", "AITECH.EMBEDDING"],
    "AITECH.SEMSEARCH": ["AITECH.EMBEDDING"],
    "AITECH.VECTORDB": ["AITECH.EMBEDDING"],
    "AITECH.FINETUNE": ["AITECH.LLM", "FRAMEWORK.PYTORCH"],
    "AITECH.LORA": ["AITECH.FINETUNE"],
    "AITECH.DPO": ["AITECH.FINETUNE"],
    "AITECH.RLHF": ["AITECH.FINETUNE"],
    "AITECH.AGENT": ["AITECH.LLM", "AITECH.PROMPT"],
    "AITECH.FUNCALL": ["AITECH.LLM"],
    "AITECH.MCP": ["AITECH.LLM"],
    "AITECH.INFER_ACC": ["AITECH.LLM"],
    "FRAMEWORK.VLLM": ["AITECH.LLM", "AITECH.INFER_ACC"],
    "AITECH.DISTRIBUTED": ["FRAMEWORK.PYTORCH"],
    "FRAMEWORK.DEEPSPEED": ["AITECH.DISTRIBUTED"],
    "FRAMEWORK.MEGATRON": ["AITECH.DISTRIBUTED"],
    "ENGINEERING.ASCEND": ["AITECH.DISTRIBUTED"],
    # 工程
    "ENGINEERING.DOCKER": ["ENGINEERING.LINUX"],
    "ENGINEERING.K8S": ["ENGINEERING.DOCKER"],
    "ENGINEERING.CICD": ["ENGINEERING.GIT"],
    "ENGINEERING.MLOPS": ["ENGINEERING.DOCKER", "ENGINEERING.CICD"],
    "ENGINEERING.CUDA": ["PROG.C", "PROG.CPP"],
    "ENGINEERING.FASTAPI": ["PROG.PYTHON"],
    "ENGINEERING.FLASK": ["PROG.PYTHON"],
    "ENGINEERING.DJANGO": ["PROG.PYTHON"],
}

_STAGE_META = {
    "P0": ("阶段 1 · 补齐硬性门槛", "先拿下 JD 里明确要求的技能，否则简历容易被直接筛掉"),
    "P1": ("阶段 2 · 提升竞争力", "高频需求技能，补上后匹配度与面试通过率明显提升"),
    "P2": ("阶段 3 · 拉开差距", "加分项，有余力再补，可用于简历亮点或方向探索"),
}

# 资源类型 -> 学习动作模板
_ACTION_BY_TYPE = {
    "course": "跟完课程，完成全部练习，并整理一份自己的笔记",
    "book": "按章节精读，动手敲一遍书中示例代码",
    "paper": "精读论文 + 复现核心实验（至少跑通最小配置）",
    "doc": "读官方文档，跑通一个最小可运行示例",
    "blog": "读教程并复现示例，记录踩坑点",
}


@dataclass
class LearningStep:
    skill_id: str
    name: str
    priority: str
    difficulty: int
    hours: int
    actions: list = field(default_factory=list)
    resources: list = field(default_factory=list)
    prereq_note: str = ""


@dataclass
class LearningStage:
    phase: str            # 阶段标题
    goal: str
    weeks: int
    hours: int
    steps: list = field(default_factory=list)


@dataclass
class LearningPath:
    stages: list = field(default_factory=list)
    total_hours: int = 0
    total_weeks: int = 0
    # 用户已标记「已学完」而跳过的技能名（保持缺失清单原顺序，便于页面说明）
    skipped: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_hours": self.total_hours,
            "total_weeks": self.total_weeks,
            "skipped": list(self.skipped),
            "stages": [
                {
                    "phase": s.phase, "goal": s.goal, "weeks": s.weeks, "hours": s.hours,
                    "steps": [
                        {
                            "skill_id": st.skill_id, "name": st.name, "priority": st.priority,
                            "difficulty": st.difficulty, "hours": st.hours,
                            "actions": list(st.actions), "resources": list(st.resources),
                            "prereq_note": st.prereq_note,
                        }
                        for st in s.steps
                    ],
                }
                for s in self.stages
            ],
        }


def hours_for(difficulty: int) -> int:
    """难度 -> 预估学时（越界值夹到 1~5；None/非法值按 3 处理）。"""
    try:
        d = int(difficulty) if difficulty is not None else 3
    except (TypeError, ValueError):
        d = 3
    d = max(1, min(d, 5))
    return HOURS_BY_DIFFICULTY[d]


def _actions_for(resources: list) -> list[str]:
    """按资源类型给出学习动作；最后统一附一条「最小项目」动作。"""
    actions, seen = [], set()
    for r in resources or []:
        t = str((r or {}).get("type") or "").strip().lower()
        act = _ACTION_BY_TYPE.get(t)
        if act and act not in seen:
            seen.add(act)
            actions.append(act)
    actions.append("做一个能写进简历的最小项目：输入/输出明确，能量化效果（准确率、耗时、召回等）")
    return actions


def _order_by_prereq(items: list) -> list:
    """阶段内按先修关系拓扑排序；同层按 priority_score 降序（稳定）。"""
    by_id = {i["skill_id"]: i for i in items}
    ordered, visited = [], set()

    def visit(sid, stack=()):
        if sid in visited or sid not in by_id or sid in stack:
            return
        for pre in SKILL_PREREQS.get(sid, []):
            visit(pre, stack + (sid,))
        visited.add(sid)
        ordered.append(by_id[sid])

    for it in sorted(items, key=lambda x: -float(x.get("priority_score") or 0.0)):
        visit(it["skill_id"])
    return ordered


def build_learning_path(missing: list, *, hours_per_week: int = 10,
                        taxonomy=None, learned=()) -> LearningPath:
    """把差距报告里的缺失项排成可执行的学习路径。

    missing: list[GapItem]（需含 skill_id/name/priority/difficulty/priority_score/resources）
    hours_per_week: 每周可投入学时（<=0 时按 10 计）
    taxonomy: 可选，用于把「不在缺口内」的前置技能翻成可读名称
    learned: 已标记「已学完」的 skill_id 集合。命中的技能不再进入路径（计入
             `path.skipped`），并且视为已具备先修——不再提示「前置技能不在缺口内」。
    """
    weekly = int(hours_per_week) if int(hours_per_week or 0) > 0 else 10
    learned_ids = {str(x).strip() for x in (learned or ()) if str(x).strip()}
    path = LearningPath()
    items = []
    for m in missing or []:
        sid = getattr(m, "skill_id", None)
        if not sid:
            continue
        name = getattr(m, "name", sid) or sid
        if sid in learned_ids:          # 已学完 → 从剩余计划里移除
            path.skipped.append(name)
            continue
        items.append({
            "skill_id": sid,
            "name": name,
            "priority": getattr(m, "priority", "P2") or "P2",
            "difficulty": int(getattr(m, "difficulty", 3) or 3),
            "priority_score": float(getattr(m, "priority_score", 0.0) or 0.0),
            "resources": list(getattr(m, "resources", []) or []),
        })

    # 先修若落在更靠后的阶段，把它提到前面（否则按顺序学不动）
    stage_idx = {"P0": 0, "P1": 1, "P2": 2}
    stage_of = {it["skill_id"]: stage_idx.get(it["priority"], 2) for it in items}
    changed = True
    while changed:
        changed = False
        for it in items:
            cur = stage_idx.get(it["priority"], 2)
            for pre in SKILL_PREREQS.get(it["skill_id"], []):
                if pre in stage_of and stage_of[pre] > cur:
                    stage_of[pre] = cur
                    changed = True
    for it in items:
        it["priority"] = next(p for p, i in stage_idx.items()
                              if i == stage_of[it["skill_id"]])

    present = {g["skill_id"] for g in items} | learned_ids
    for p in ("P0", "P1", "P2"):
        group = [it for it in items if it["priority"] == p]
        if not group:
            continue
        steps = []
        for it in _order_by_prereq(group):
            prereqs = SKILL_PREREQS.get(it["skill_id"], [])
            note = ""
            missing_pre = [x for x in prereqs if x not in present]
            if missing_pre:
                names = []
                for pid in missing_pre:
                    sk = taxonomy.by_id(pid) if taxonomy is not None else None
                    names.append(sk.name if sk else pid)
                note = "前置技能不在本岗位缺口内，若完全不熟悉建议先补：" + "、".join(names)
            steps.append(LearningStep(
                skill_id=it["skill_id"],
                name=it["name"],
                priority=it["priority"],
                difficulty=it["difficulty"],
                hours=hours_for(it["difficulty"]),
                actions=_actions_for(it["resources"]),
                resources=it["resources"],
                prereq_note=note,
            ))
        stage_hours = sum(s.hours for s in steps)
        phase, goal = _STAGE_META[p]
        path.stages.append(LearningStage(
            phase=phase, goal=goal,
            weeks=max(1, math.ceil(stage_hours / weekly)),
            hours=stage_hours, steps=steps,
        ))

    path.total_hours = sum(s.hours for s in path.stages)
    path.total_weeks = sum(s.weeks for s in path.stages)
    return path


def format_path_markdown(path: LearningPath, *, hours_per_week: int = 10) -> str:
    """学习路径 -> Markdown（页面与导出复用，纯函数）。"""
    if not path.stages:
        if path.skipped:
            return (f"已按「已学进度」跳过 {len(path.skipped)} 个已掌握技能"
                    f"（{'、'.join(path.skipped)}），暂无需要学习的技能。")
        return "暂无缺失技能，无需学习路径。"
    lines = [f"**总计**：{path.total_hours} 学时，约 {path.total_weeks} 周"
             f"（按每周 {hours_per_week} 小时估算）", ""]
    if path.skipped:
        lines[0:0] = [f"> 已按「已学进度」跳过 {len(path.skipped)} 个已掌握技能："
                      f"{'、'.join(path.skipped)}", ""]
    for st in path.stages:
        lines.append(f"### {st.phase}（{st.hours} 学时 / 约 {st.weeks} 周）")
        lines.append(f"> {st.goal}")
        for i, step in enumerate(st.steps, 1):
            lines.append(f"{i}. **{step.name}** · 难度 {'★' * step.difficulty}"
                         f"{'☆' * (4 - min(step.difficulty, 4))} · 约 {step.hours} 学时")
            if step.prereq_note:
                lines.append(f"   - {step.prereq_note}")
            for act in step.actions:
                lines.append(f"   - {act}")
            for r in step.resources[:2]:
                title, url = (r or {}).get("title", ""), (r or {}).get("url", "")
                lines.append(f"   - 资源：[{title}]({url})" if url else f"   - 资源：{title}")
        lines.append("")
    return "\n".join(lines).strip()


def _demo() -> int:
    from pathlib import Path

    import yaml

    from src.matcher.gap_analyzer import SkillGapAnalyzer
    from src.skillkb.loader import Taxonomy

    root = Path(__file__).resolve().parents[2]
    tax = Taxonomy(str(root / "data" / "kb" / "skill_taxonomy.yaml"))
    res = yaml.safe_load((root / "data" / "kb" / "learning_resources.yaml").read_text(encoding="utf-8"))
    analyzer = SkillGapAnalyzer(tax, resources=res)
    jd = [
        {"skill_id": "PROG.PYTHON", "name": "Python", "is_must": True},
        {"skill_id": "FRAMEWORK.PYTORCH", "name": "PyTorch", "is_must": True},
        {"skill_id": "ML.TRANSFORMER", "name": "Transformer", "is_must": True},
        {"skill_id": "AITECH.RAG", "name": "RAG", "is_must": False},
    ]
    rep = analyzer.analyze([], jd, demand={"AITECH.RAG": .5, "ML.TRANSFORMER": .3})
    path = build_learning_path(rep.missing, taxonomy=tax)
    print(format_path_markdown(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(_demo())
