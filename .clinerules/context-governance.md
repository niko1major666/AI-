# 上下文治理（强制）

适用：本仓库的 Cline 会话。目标是把上下文膨胀挡在入口，而不是事后救火。
技能与脚本：`~/.agents/skills/context-governance/`（`SKILL.md` + `scripts/`）。

1. **任务书优先**：写任务书、派发或 fork 子 agent、拆分并行任务前，先加载 `context-governance` 技能，
   用 `make_taskbook.py` 生成任务书，再跑 `check_taskbook.py`，**0 FAIL 才可派发**。
2. **大输出折叠**：单条工具输出预计 > 8 KB（日志 / JSON / 全量测试结果）时，先跑
   `fold_tool_output.py --max-chars 1200`；只把折叠结果与原文路径带进上下文，禁止整段贴回。
3. **交接收敛**：跨会话 / 跨 agent 汇报只回传「结论 + 证据指针（`path:line` / commit / 一行命令输出）」，
   不回灌过程、日志或 diff 全文。
4. **诊断先测量**：怀疑上下文膨胀时先跑 `measure_context.py --latest --tree`，
   按五类主因（入口过宽 / 嵌套过深 / 内部未收敛 / 工具输出未压缩 / 交接回灌）给证据，不靠感觉。
5. **派生单层**：子 agent 不得再派生；需要拆分层级就回主窗重新出任务书。

> 只在这些触发条件下加载技能；不要「每轮都读一遍」，那本身就是在烧上下文。
