# 数据扩充 SOP（加公司 / 加数据源）

> 目标：**一次做对**。加数据前先读 `docs/metrics.md` 拿基线；任何改动都必须先让
> `python scripts/preflight_new_source.py` 没有 FAIL，才允许进 `merge_jobs` / `build_dataset`。
> 这份文档是「加数据会踩哪些坑」的唯一记忆点，改流程时同步更新这里。

## 0. 一句话流程

```
爬取 → data/raw/<company>_ai_jobs.csv（10 列 / job_id 带源前缀 / 统一中文公司名）
     → 双处注册（merge_jobs.FILES + recrawl_all.CRAWLERS）
     → 体检 python scripts/preflight_new_source.py --source <csv>   ← 唯一闸门
     → merge_jobs.py → build_dataset --stats
     → recalc_importance.py（占比有变化时）→ eval_all.py
     → 同步常量/文档 → 全量 pytest → 提交
```

## 1. 摄入格式（新爬虫必须遵守）

| 约束 | 原因 |
|---|---|
| 列名用 `CANON_COLS`：`job_id, company, title, location, salary, experience, education, jd_text, department, publish_time` | `configs/dataset.yaml` 的 `column_mapping` 是全局的，规范列名可零改配置接入 |
| `job_id` **必须带源前缀**（`ks_` / `kimi_` / `hw51_` / `xhs_` / 自建 `ali_`） | `merge_jobs` 按 `job_id` `keep="first"` 去重，撞车 = 静默丢行（体检报 FAIL） |
| `company` 用**统一中文名** | `normalize_company()` 只去后缀/括号/小写，**没有别名表**，「阿里」与「阿里巴巴」会算成两家 |
| 正文放 `jd_text`，岗位名放 `title` | 标题黑/白名单只作用于 `title`，不做正文过滤 |
| CSV 落在 `data/raw/`，**不要提交** | `.gitignore` 例外只有 `data/raw/sample_jobs.csv`；语料走 `data/processed/jobs.jsonl` |

## 2. 双处注册（漏一处就静默不进语料）

- `scripts/merge_jobs.py` 的 `FILES`（合并顺序 = 去重时的保留优先级）
- `scripts/recrawl_all.py` 的 `CRAWLERS`（一键重爬能看到它）

> 已知硬化债：`merge_jobs.py` / `analyze_skills.py` / `verify_real.py` 里仍是
> `ROOT = Path("D:/ai-skill-gap")` 绝对路径，换机器要先改成仓库相对路径。

## 3. 体检（`scripts/preflight_new_source.py`，只读，约 2 秒）

```powershell
# 单源（venv 已激活；也可写成 .\.venv 下的 python.exe 前缀）
python scripts/preflight_new_source.py --source data/raw/ali_ai_jobs.csv

# 多源一起看（模拟这一批一起进语料）+ 落 JSON 供后续比对
python scripts/preflight_new_source.py --source a.csv --source b.csv --json preflight.json
```

| 检查项 | FAIL / WARN 条件 | 处理 |
|---|---|---|
| 必需列 | `job_id/company/title/jd_text` 整列为空 → FAIL | 改 `column_mapping`（别名）或重出 CSV |
| 可用行 | 清洗后 0 行 → FAIL | 检查 `jd_text` 是否选错列 |
| job_id | 与现有语料冲突 / 源内重复 → FAIL；缺 id → WARN | 加源前缀后重跑；缺 id 重建会漂移 |
| 正文重复 | 与现有语料重复 / 源内重复 → WARN | 看明细：重复行会被丢；若新源放最前会覆盖旧行、改写公司归属 |
| 公司写法分裂 | 同归一多写法（跨源/源内）→ WARN | 合并前统一公司名（别名表尚未实现） |
| 新源零技能率 | > 30% → WARN | 多为「整站列表式短 JD」，会让零技能兜底变重 |
| 合并后零技能占比 | 出 `20%~28%` → FAIL | 见 §5 阈值表；必要时调整上游采集或口径 |
| 合并后技能覆盖 | < 159 → FAIL | 说明新语料没带来新技能，或抽取词表漏了（看 `skills` 列缺口） |
| 硬性要求占比 | 相对现有语料偏移 > 3pt → WARN | 通常说明新源 JD 风格差异大（列表式/英文），不影响正确性 |
| 自带 skills 列覆盖 | 有未覆盖技能（≥2 次）→ WARN | 考虑补进 `data/kb/skill_taxonomy.yaml`（补完跑 `validate_kb.py` + `recalc_importance.py`） |

退出码：有 FAIL → `1`（可当 CI/脚本闸门），只有 PASS/WARN → `0`。
阈值参数 `--zero-skill-band` / `--min-skill-coverage` 默认值写在脚本顶部常量里，
**与 `tests/test_dataset_snapshot.py` 的 slow 用例保持一致**，改一处就要改另一处。

## 4. 合并与构建（看这些 stats 字段）

```powershell
.\\.venv\\Scripts\\python.exe scripts/merge_jobs.py            # → data/raw/all_jobs.csv
.\\.venv\\Scripts\\python.exe -m src.data.build_dataset --stats  # → data/processed/jobs.jsonl
```

## 5. 构建后必改清单（一处漏改 = CI 红）

| 位置 | 要改什么 |
|---|---|
| `tests/test_dataset_snapshot.py` | 精确常量 `4582 / 78 / 4472`；slow 用例的「零技能占比 `0.20~0.28`」「技能覆盖 ≥ `159`」 |
| `tests/test_skillkb.py` | 个别技能 importance 断言（如 `PROG.PYTHON=5`、`BIGDATA.FLINK=3`）——占比变了就要重跑 `recalc_importance.py` 再对齐 |
| `scripts/preflight_new_source.py` | `ZERO_SKILL_BAND` / `MIN_SKILL_COVERAGE`（与 snapshot 测试同步） |
| `docs/metrics.md` | `python scripts/eval_all.py` 生成，CI 在 main 上 `git diff --exit-code` 校验是否过期 |
| `README.md` | 数据源表「条数」+ 公司分布行 + 量化指标段 + 路线图新增 W 行 |
| `PROJECT_REPORT.md` | §四 各源条数、§五 数据规模 / 零技能 / must 占比 |
| `memory-bank/*` | `activeContext`（当前状态）、`progress`（本轮记录）、`techContext`（测试数）、`systemPatterns`（口径） |
| 三处模块 docstring | `src/matcher/job_neighbors.py`（零技能 1162 / 25.4% / 97.9%）、`src/matcher/jd_requirements.py`（56.5% / 3420 / 4830·175·1804）、`src/extractor/rule_baseline.py`（4582） |

## 6. 当前基线（迭代 6 之后，2026-10）

| 指标 | 值 | 来源 |
|---|---|---|
| 语料 | 4582 条 / 78 家 / 4472 唯一「公司+标题」 | `build_stats.json` |
| 原始抓取 | 5013 条（过短 7 + 标题过滤 4 + 重复 420） | 同上 |
| 零技能岗位 | 1162 条（25.4%），97.9% 可同公司代理 | `job_neighbors`、`docs/metrics.md` |
| 有技能岗位 | 3420 条（must 判定的分母） | `jd_requirements` |
| 技能覆盖 | 160/161（缺「联邦学习」，语料未出现） | `test_dataset_snapshot` slow |
| 学习资源 | 106/161（65.8%） | `learning_resources.yaml` |
| 硬性要求 | 56.5% 岗位 / 1.49 项每岗（句内 4830 · 章节 175 · 兜底 1804） | 体检脚本 `[6]` 段可复现 |
| 抽取 F1 | test 0.9565 / 全量 0.9123 | `docs/metrics.md` |

**单公司零技能率**（决定「还能不能加列表式短 JD」）：
小红书 37.4%、快手 32.5%、Kimi 20%、小米 19.8%、腾讯 16.6%、字节 5.0%、英文岗 ~0%。
→ 再加约 1800 条列表式 JD 会把整体推到 **28.3%**，正好撞上 nightly 的 28% 上界。

## 7. 五个静默坑（脚本已覆盖，人工评审也别放过）

1. **job_id 撞车**：`merge_jobs` 按 `job_id` `keep="first"`，撞车丢行无日志。
2. **正文跨源重复**：`build_dataset` 按 `text_hash` `keep="first"`，**公司归属由 `FILES` 顺序决定**（当前存有 30 条跨文件重复文本）。
3. **公司别名不合并**：78 家是「归一后」的 78；加源时若写法不同，公司数会虚增。
4. **整站列表式短 JD**：抽取为空 → 零技能率上升 → `job_neighbors` 对「整站列表」会返回空，页面重新出现「匹配度 0% + 已覆盖全部技能」的矛盾。
5. **标题黑名单只作用于构造期**（`src/data/job_filter.py`）：白名单保留「测试/数据/智能」，放宽时要看 `dropped_offtopic` 抽样。

## 8. 已知缺口（按优先级）

1. `company_aliases` 配置 + 接进 `normalize_company()`——体检只能报「写法分裂」，不能自动合并。
2. `merge_jobs.py` / `analyze_skills.py` / `verify_real.py` 的 `ROOT = Path("D:/ai-skill-gap")` 改仓库相对路径。
3. `data/processed/jobs.jsonl`（13.6MB）入库而 `data/raw/*` 不入库 ⇒ **语料不可复现**，每次扩数据多一个二进制 blob；建议 raw 走 Release 附件或 Git LFS。
4. 代理（`job_neighbors`）对「无可用相似岗位的公司」缺兜底文案，扩源后要复测。

## 9. 成本参考（本机 CPU）

| 动作 | 耗时 |
|---|---|
| 读 `jobs.jsonl`（13.6MB） | 0.09s |
| 全语料规则抽取 | 0.84s（0.18s/1000 行） |
| preflight（抽取 + 合并预测 + must 判定） | ~2.0s |
| 全量 pytest | ~40s（213→222 条后仍 < 1min） |

## 10. 自检清单（复制到 PR / 提交说明里）

- [ ] 新 CSV 10 列齐全、`job_id` 带源前缀、公司名统一
- [ ] `merge_jobs.FILES` + `recrawl_all.CRAWLERS` 双处注册
- [ ] preflight 无 FAIL（WARN 已逐条确认，正文重复/公司分裂已知情）
- [ ] `build_dataset --stats` 的 `cleaned_rows` 与体检预测吻合
- [ ] `validate_kb.py` 通过；补过技能则 `recalc_importance.py` 后无差异
- [ ] `eval_all.py` 生成新 `docs/metrics.md` 并一起提交
- [ ] 四处常量（snapshot / skillkb / preflight / metrics）已同步，三处 docstring 已改
- [ ] README / PROJECT_REPORT / memory-bank 数字已改
- [ ] 全量 pytest 通过；CI（`metrics` + `test (3.10)` + `test (3.12)`）绿

