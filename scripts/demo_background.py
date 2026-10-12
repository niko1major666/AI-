"""对真实简历做背景技能识别 + AI 迁移建议，输出到 UTF-8 文件。"""
import sys
from pathlib import Path

import yaml

ROOT = Path("D:/ai-skill-gap")
sys.path.insert(0, str(ROOT))

from src.matcher.gap_analyzer import SkillGapAnalyzer
from src.skillkb.loader import Taxonomy

taxonomy = Taxonomy(str(ROOT / "data" / "kb" / "skill_taxonomy.yaml"))
tm = yaml.safe_load((ROOT / "data" / "kb" / "transfer_map.yaml").read_text(encoding="utf-8"))
analyzer = SkillGapAnalyzer(taxonomy, transfer_map=tm)

text = (ROOT / "models" / "resume_text.txt").read_text(encoding="utf-8")
lines = text.splitlines()
start = 0
for i, l in enumerate(lines):
    if l.startswith("----"):
        start = i + 1
        break
resume = "\n".join(lines[start:])

bg = analyzer.detect_background(resume)
out = [f"识别到 {len(bg)} 组道桥背景技能，对应 AI 迁移建议如下：", ""]
for b in bg:
    out.append(f"【{b['source_skill']}】")
    out.append(f"  匹配关键词：{'、'.join(b['keywords'])}")
    out.append(f"  → 可迁移 AI 技能：{'、'.join(b['targets'])}")
    out.append(f"  理由：{b['rationale']}")
    out.append(f"  行动建议：{b['action']}")
    out.append("")
(ROOT / "models" / "bg_result.txt").write_text("\n".join(out), encoding="utf-8")
print("matched", len(bg))
