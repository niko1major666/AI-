# 进度（Progress）

## 什么能用（已完成）
- ✅ 数据采集：5832 条真实 JD / 81 家公司（腾讯/字节/小米/DeepSeek/华为/Kimi/MiniMax/快手/小红书/美团/滴滴/哔哩哔哩 + 英文科技岗位），含部门/发布时间等字段
- ✅ 技能抽取：规则基线（F1 0.957）+ BERT-NER（exact 0.636 / overlap 0.909，已恢复旧模型），161 技能（难度+重要度）
- ✅ 语义匹配：TF-IDF + BGE；口语化句子评测 Recall@5：BGE 0.54 vs TF-IDF 0.24（147 技能词表时期；161 技能下 TF-IDF 当前基线 0.2200，见 `docs/metrics.md`）
- ✅ 差距诊断：匹配度 + 缺失技能全清单 + P0/P1/P2 优先级 + 重要度（数据驱动）+ 难度 + 学习资源；AI 解读按简历专业生成迁移建议（无专业不展示）
- ✅ 简历解析：正则 + DeepSeek LLM 增强（姓名/工作经历/完整专业名）+ ATS 改进建议
- ✅ 前端：Streamlit 三页面（技能图谱/简历匹配/差距报告），卡片式 UI、星级展示
- ✅ 工程：284 测试全通过（282 快测 + 2 slow；含保活脚本纯函数测试 + 小红书/哔哩哔哩/美团/滴滴爬虫解析测试 + 岗位标题过滤 + 岗位收藏纯函数）、Docker、报告导出 Word、README + 项目报告
- ✅ 云端部署：依赖分层（requirements.txt 轻量 / requirements-ml.txt 重模型）、清洗数据 jobs.jsonl 入库、Streamlit secrets 支持、sys.path 兼容（Streamlit Community Cloud）
- ✅ SSH 推送：生成 ed25519 key + `~/.ssh/config` + 公钥，main 分支已同步远程（`niko1major666/AI-`）
- ✅ GitHub 发行：public 仓库 + Description/Topics + MIT License + Release v1.0.0 + GitHub Actions CI（66 测试绿）+ README 三页面截图/徽章/在线体验链接
- ✅ 发行 v1.4.0（2026-10-26）：数据源扩充三家（哔哩哔哩 194 + 滴滴 387 + 美团 669），语料 4582→5832 条 / 81 家、零技能 25.4%→21.5%、must 56.5%→60.0%、测试 203→267；`docs/release-notes/v1.4.0.md` + 附注 tag，`release.yml` 自动建 Release；README 目录结构两处过期数字（13 爬虫模块 / 14 数据源、267 用例）同时修
- ✅ LLM 生成式报告解读 + 学习计划：report_interpreter（DeepSeek，LLM 优先/模板兜底），差距报告页新增「AI 解读 + 学习计划」区块
- ✅ 快手爬虫：社招（逆向 sign HMAC-SHA256）+ 校招（POST 无 sign），共 1396 条完整 JD
- ✅ DeepSeek 详情：33 条从列表升级为完整 JD（平均 1267 字）
- ✅ BERT-NER 旧模型恢复：restore_ner.py 从 bert-base-chinese 重训 30 条人工标注，exact 0.545→0.636
- ✅ 简历解析优化：工作经历细粒度（职责/量化成果/技术栈）、work_years 正则 bug 修复、LLM skills 补充技能抽取、ATS 建议增强（姓名/经历完整性/量化）
- ✅ 云端保活（已修复）：GitHub Actions 每 6 小时探测 `/~/+/_stcore/health`（200 `ok` = 就绪 / 400 = 休眠），Playwright 建真实会话、休眠时点按钮并轮询 health 至就绪（冷启动实测 262 s），本地 `scripts/keepalive_app.py`（`--no-browser` 快速自检），交互式 `scripts/keepalive.sh`
- ✅ 小红书爬虫：`pageQueryPosition` 直连（无需签名）社招 864 + 校招 508，清洗后 1284 条完整 JD（含 jobType / publishTime），数据 3302→4586 条 / 78 家
- ✅ 技能重要度重算（4586 条语料）：147 技能中 9 升 / 34 降 / 104 不变；新分布 1:73、2:22、3:29、4:12、5:11；Top 大模型 36.2%、Python 36.0%、智能体 22.3%；同步更新 `test_skillkb` / `test_gap_analyzer` 分档断言
- ✅ 岗位标题过滤器：`src/data/job_filter.py`（黑名单：土木/建筑/施工/结构工程师等 34 词 + 白名单：AI/算法/数据等 31 词保护），`configs/dataset.yaml` 可开关与覆盖词表；构建时剔除 4 条非 AI 工程岗（4586→4582），重要度分档未变；新增 `tests/test_job_filter.py`（7 用例，含管线接入与禁用场景）
- ✅ 发行流水线：`.github/workflows/release.yml`（push `v*` tag → `gh release create`，Release 已存在时改走 `gh release edit` 更新正文；标题取 `docs/release-notes/<tag>.md` 首行），已发布 v1.2.0 / v1.3.0；`scripts/capture_screenshots.py` 可一键重截 README 预览图
- ✅ 迭代 1（缺陷修复）：`is_must` 由「全语料需求占比 ≥ 40%（实测最高 36.2% → 恒 False）」改为 `src/matcher/jd_requirements.py` 三级判定（句内触发词 → 章节标题 → 占比兜底），57.0% 岗位可判出硬性要求（1.48 项/岗）；零技能岗位（1085 条）改用 `src/matcher/job_neighbors.py` 同公司相似岗位代理（覆盖 98.7%，中位 4 项）并标注来源，不再误显示「已覆盖全部技能」；匹配度加入岗位内强调度 `base × (1 + ln tf)`（45.2% 岗位有 tf≥2）；`rule_baseline.extract()` 单次扫描同时产出 span + 词频（避免冷启动 9s→18s）；简历解析按文本缓存 + LLM 超时 90s→25s 重试一次；测试 108 → 122
- ✅ 迭代 2（KB 内容补全）：技能 147 → 161 —— 新增 16 项 JD 高频缺失技能（视觉语言模型 5.87%、Function Calling 4.60%、MCP 2.75%、视频生成 2.58%、扩散模型 2.36%、偏好对齐 1.70%、昇腾 1.70%、长上下文 1.16%、DeepSeek 1.05%、Qwen / Llama / GLM / 世界模型 / 具身智能 / LangGraph / Dify），合并 2 个零命中冗余项（文本向量化→Embedding、华为云→云计算，别名保留）；学习资源 11 → 106 项（覆盖 Top 80 需求技能中的 77 项）；新增 `Skill.skip_extract` 机制修正「量化」误匹配（6.31% → 1.07%，importance 4→2，简历侧仍能解析「量化」）；技能命中 160/161（仅「联邦学习」语料未出现），抽取全语料 11.0s；新增 `tests/test_learning_resources.py`（6 用例）+ 词表/抽取回归用例，测试 122 → 131
- ✅ 迭代 3（功能扩展 C1–C7 + 评测/CI 加固 D1–D7）：
  - C1 规则版学习路径 `src/matcher/learning_path.py`（P0/P1/P2 三阶段 + 先修拓扑排序 + 难度→学时 + 周数，无 API key 也出计划，`prereq_note` 提示缺口外前置）
  - C2 报告导出 `src/app/report_export.py`（Markdown / docx，文件名清洗；报告存 session，`download_button` rerun 后仍可下载）
  - C3 多岗位对比 `src/matcher/job_compare.py`（匹配度、P0 数、共性缺口、各岗独有缺口、优先投递）
  - C4 公司 × Top 12 技能矩阵 `src/data/skill_stats.py`（技能图谱页 ProgressColumn 条形表，不引新依赖）
  - C5 简历补强建议 `src/data/resume_advice.py`（原文命中→改写要点，未命中→小项目建议，数字一律占位符不编造）
  - C6 反向岗位推荐 `src/matcher/job_recommender.py`（按「公司+标题」去重，must/nice 加权，Top 10 + 最该补 3 项，`st.cache_data` 缓存）
  - C7 技能画像 `src/matcher/strength_profile.py`（按类别的需求加权覆盖率 + 最大短板）
  - D1/D2 指标回归测试：抽取 F1（test 0.9565 / 全量 0.9123，容差 1pt）、TF-IDF Recall@5（skill_pair 0.9750 / resume_sentence 0.2200，容差 2pt）
  - D3 语料快照：5832 条 / 81 家 / 5645 唯一「公司+标题」/ 字段与 job_id 唯一（slow 用例校验全语料 160/161 覆盖、零技能占比 20~28%）
  - D4/D5 CI：覆盖率门槛 55%（实测 58%）+ Python 3.10/3.12 矩阵 + pip 缓存 + concurrency；`slow` 标记（全语料遍历）由 nightly 全量跑
  - D6 `scripts/eval_all.py` → `docs/metrics.md`（抽取/匹配/覆盖/阈值四节，无时间戳可 diff），CI main 分支校验报告未过期
  - D7 `scripts/validate_kb.py`（词表 id/别名冲突/类别/难度 + 资源 skill_id/重复 title/非法 url）+ `compileall`，CI 前置拦截
  - 测试 131 → 201（迭代 3）→ 203（v1.3.1）→ 207（迭代 5）→ 213（迭代 6：211 快测 + 2 slow）→ 222（数据扩充工具化：220 快测 + 2 slow）→ 236（哔哩哔哩：234 快测 + 2 slow）→ 250（滴滴：248 快测 + 2 slow）→ 267（美团：265 快测 + 2 slow）→ 284（迭代 7：282 快测 + 2 slow）；快测约 38s
- ✅ README 界面预览补两张「区域截图」（`scripts/capture_screenshots.py --page company_matrix|gap_compare`）：**公司 × Top 12 技能**（技能图谱页 ProgressColumn 矩阵，行=公司按 JD 数降序、值=该公司 JD 命中比例；`demand_matrix` 由公司名字母序改为 JD 数降序，避免 1~2 条 JD 的小公司以 0%/100% 占满首屏，新增 `test_matrix_companies_sorted_by_job_count_desc`）与**多岗位对比初始界面**（差距报告页第二种模式：选公司 → 勾 2~4 岗 → 技能留空沿用简历匹配结果 → 开始对比）；脚本新增区域裁剪（`stMainBlockContainer` 定宽 + 内层 `stMain` 滚动，因为 Streamlit 不滚 window）、模式切换与公司下拉选择，`--page all` 一次出 3 整屏 + 2 区域共 5 张；两段介绍改用实测数字（Top 12 需求占比、跨公司对比、31/78 家 JD≤2 的读图提示）
- ✅ 迭代 6（抽取口径 + 学习路径联动）：`ENGINEERING.UNITTEST` 加 `skip_extract: [测试]`（JD 命中 521 条 / 11.37% → 13 条 / 0.28%，其中 508 条只靠裸「测试」；`recalc_importance` 后 importance 5→1；gold F1 三项零变化，新增 `test_skip_extract_ignores_generic_testing_words` / `test_unittest_alias_only_for_user_input`）；`build_learning_path(..., learned=...)` 支持「已学进度」——命中的技能移出路径并计入 `path.skipped`、视作已具备先修（不再提示前置缺口），页面差距报告改为 session 渲染（勾选即时重排、报告不再因 rerun 消失），AI 解读按「岗位 + 技能」缓存避免重复调用；新增 4 个 `test_learning_path` 用例 + AppTest 勾选回归，测试 207 → 213
- ✅ 数据扩充工具化（已随 v1.4.0 发布）：`scripts/preflight_new_source.py` 只读体检——把「加数据 → 常量/阈值/文档同时红」的判断前移：清洗结构、job_id 冲突（`merge_jobs` keep=first 静默丢行）、正文跨源重复（`build_dataset` text_hash keep=first，公司归属看 FILES 顺序）、公司写法分裂（无别名表）、新源零技能率、**合并后**零技能占比与技能覆盖、must 占比偏移（±3pt），并可选比对 CSV 自带 skills 列找词表缺口；退出码有 FAIL 即 1，可作为合并前的闸门。现有语料自检复现 4582/78/1162/160/56.5%/1.49 项每岗/句内 4830·章节 175·兜底 1804（与 `docs/metrics.md` 一致）。新增 `tests/test_preflight_new_source.py`（9 用例，含「把已在语料里的源当新数据 → 全量重复、规模不变」回归）；新增 `memory-bank/dataOnboarding.md` 作为加数据的唯一 SOP（摄入格式 / 双处注册 / 体检判定表 / 四处常量清单 / 五个静默坑 / 当前基线 / 单公司零技能率 / 成本 / PR 自检清单）
- ✅ 接入哔哩哔哩（已随 v1.4.0 发布）：`src/crawler/bilibili.py` 走匿名 CSRF（`X-AppKey` + `X-CSRF`，token 由 `api/auth/apply/csrf/token` 签发，`code=-3` 自动刷新重试一次），社招 87 + 校招 117 = 204 条（响应自带全文 JD）。全站 876 条里技术类 184（零技能 2.2%）+ AI类 20（0%），其余运营/内容/设计岗 42%~82% 零技能 → 默认只落技术/AI（`--all` 全量），体检预演全绿；合并构建后语料 4582→4776 条 / 79 家（零技能 25.4%→24.4%、must 56.5%→57.5% / 1.66 项每岗、tf≥2 45.3%、覆盖仍 160/161），`recalc_importance` 6 项微调；新增 `tests/test_bilibili.py`（14 用例），测试 222→236
- ✅ 接入滴滴（已随 v1.4.0 发布）：`src/crawler/didi.py` 用公开 GET（`recruit-portal-service/api/job/front/list`，无 token / 无签名）抓社招 1081 条，`items[]` 自带 `jobDuty` + `jobQualification` 全文。**坑：`size` 上限 100**——传 200 返回 `meta.code=10039`「拦截返回」+ `data=null`（HTTP 仍 200，只看状态码像「没岗位」），爬虫校验业务码并对「空页但只拿到 N/total」显式抛错；SPA 入口 bundle 无 `/api` 字符串，接口靠 Playwright 抓 XHR 定位（`scripts/probe_didi.py`）。技术类 423 条（零技能 11.8%、平均 5.3 项技能），运营 53.7% / 产品 65.6% / 安全 75.0% 零技能 → 默认只落技术（`--all` 全量），入语料 387 条（源内重复 35 条被去重）；校招在 Moka（列表接口返回 AES 密文）未接入。合并构建后语料 4776→5163 条 / 80 家（零技能 24.4%→23.5%、must 57.5%→57.7% / 1.69 项每岗、tf≥2 45.7%、覆盖仍 160/161），`recalc_importance` 6 项微调；新增 `tests/test_didi.py`（14 用例），测试 236→250
- ✅ 接入美团（已随 v1.4.0 发布）：`src/crawler/meituan.py` 走移动端公开 POST（`official/mobile/job/getJobList`，无 token / 签名 / cookie）抓社招 3231 条，`list[]` 自带 `jobDuty` + `jobRequirement` 全文。**三个坑**：① 分页参数必须嵌在 `page` 对象里（PC 版同名接口收顶层 `pageNo` 且把 `pageSize` 锁死 20；移动版 `pageSize` 实测上限 1000、固定用 200，17 页抓完）；② `u_query_id` / `r_query_id` 是「本次查询」token，**整轮翻页必须复用**——每页换新会被当成新搜索、永远返回第 1 页（17 页只有 200 条唯一岗位，`totalCount` 仍是 3231）→ 爬虫按 job_id 去重，并在「整页无新增」/「唯一条数 < total」时抛错；③ `jobShareType=2`（2326 条）免 token 但正文全空，固定用 `1`；接口靠 Playwright 抓 `/m/position` 的 XHR 定位（`scripts/probe_meituan.py`）。技术类 681 条（零技能 6.0%、平均 6.7 项技能），零售 90.6% / 销售客服 97.0% / 职能 71.1% / 运营 48.1% / 产品 37.0% 零技能 → 默认只落技术类（`--all` 全量 3231），入语料 669 条（源内重复 11 条被去重）；校招/实习走 PC 版 `jobType`（196 / 371 条）待接入。合并构建后语料 5163→5832 条 / 81 家（零技能 23.5%→21.5%、must 57.7%→60.0% / 1.80 项每岗、tf≥2 49.2%、覆盖仍 160/161），`recalc_importance` 16 项微调；新增 `tests/test_meituan.py`（17 用例），测试 250→267
- ✅ 迭代 7（求职闭环）：简历经历新增 `kind`（`work` / `internship` / `project` / `other`）——LLM 先判定，缺省时正则按章节标题 → 角色关键词 → 组织关键词推断，教育经历明确跳过；`ResumeProfile` 增加 `work_experiences` / `project_experiences` / `other_experiences`，简历页按类型分组展示并加类型标签，ATS 建议分别提示「缺工作/实习」与「缺项目」（全为 other 时不重复打扰）；新增 `src/matcher/job_favorites.py` 纯函数（公司+归一化标题去重、上限 20、`?fav=` 编解码、按 job_id 从语料还原），`JobSuggestion` 补 `job_id`；`app.py` 侧边栏跨页面收藏夹（查看/移除/导出 JSON），差距报告页与简历推荐 Top10 一键收藏，收藏写 `st.query_params` 刷新不丢；新增 `tests/test_job_favorites.py`（9 用例）+ 经历分类/ATS 用例 + recommender job_id 用例 + AppTest 收藏回归，测试 267→284；语料与指标不变
- ✅ 文档数字统一（以 `docs/metrics.md` 为准，`eval_all.py` 重跑零 diff）：零技能 1085→1104（24.1%）、代理 98.7%→98.1%（中位 3 项）、must 57.0%→56.8%（1.50 项/岗）、最高需求占比 36.2%→36.1%；`PROJECT_REPORT.md` 1799 条/74 家/147 技能/56 用例 → 4582/78/161/207，数据源表改「去重后」口径并补快手/小红书/Kimi/MiniMax；`techContext` 66→207 测试、8→11 源

## 量化指标（当前）
| 项 | 值 |
|---|---|
| 数据规模 | 5832 条 / 81 家公司（原始 6321 → 过短 7 + 非 AI 工程岗 6 + 重复 476） |
| 技能抽取 F1 | 规则 0.957 / BERT-NER 0.636(exact) 0.909(overlap) |
| 匹配 Recall@5 | BGE 0.54 vs TF-IDF 0.24（口语化句子，147 技能词表时期）；161 技能下 TF-IDF 当前基线 0.2200 |
| 需求强度判定 | 60.0% 岗位识别出 ≥1 项硬性要求（平均 1.80 项/岗；句内 7340 / 章节 974 / 兜底 2191） |
| 零技能兜底 | 1252 条零技能岗位（21.5%）中 98.1% 可代理，中位 3 项技能 |
| KB 技能覆盖 | 160/161 技能可在 JD 中命中（未命中：联邦学习）；161 = 147 + 新增 16 - 合并 2 |
| 学习资源覆盖 | 106/161 技能（65.8%），Top 80 需求技能覆盖 76 项 |
| 回归基线 | 抽取 F1 0.9565(test)/0.9123(全量)、TF-IDF Recall@5 0.9750/0.2200；`docs/metrics.md` 自动生成 |
| 测试 | 284 用例（282 快测 + 2 slow nightly）；覆盖率 58%，CI 门槛 55% |

## 待构建（按价值）
1. 阿里/智谱数据补充（需探查招聘渠道）
2. 美团校招 / 实习（PC 版 `jobType`，校招 196 / 实习 371，JD 齐全）与滴滴校招（Moka AES 密文）补齐
3. `company_aliases` 别名表接进 `normalize_company()`；`merge_jobs` / `analyze_skills` / `verify_real` 的绝对路径改相对
4. 岗位订阅/提醒（收藏夹已交付）；BGE 进 CI（模型缓存化，可复现 0.54 vs 0.24 的对比）

## 当前状态
- Streamlit 运行中：http://localhost:8501
- 云端部署已就绪：Streamlit Community Cloud（secrets 填 `DEEPSEEK_API_KEY`，详见 README「云端部署」）
- DeepSeek API key 已配置到用户环境变量
- 首屏冷启动（v1.3.1）：全语料抽取 24.3s → 1.5s（`str.find` 替代逐 token `re.finditer`，输出逐条一致），默认首屏不再 import sklearn；本机 AppTest 首屏 32s → 3.9s
- 版本元数据（v1.3.1）：`pyproject.toml` 的 `version` 由 `0.1.0` 对齐为 `1.3.1`；README 加动态 Release 徽章 + 「版本与发布」章节 + 路线图 W10；新增 `docs/RELEASING.md`（含重打 tag 路径）与 `tests/test_release_metadata.py`（pyproject 版本必须等于最新 `docs/release-notes/vX.Y.Z.md`，漏改即红）
- git 工作区干净，main 与远程一致；tag **v1.4.0** 已发布（数据源扩充：哔哩哔哩 / 滴滴 / 美团，正文 `docs/release-notes/v1.4.0.md`；上一版本 v1.3.1「首屏冷启动 + 3.10 CI 修复」）
- CI 绿：GitHub Actions 全绿（`metrics` + `test (3.10)` + `test (3.12)`；`-m "not slow"`，nightly 跑含 slow 的全量）；**3.10 与 3.12 都跑快测 282 用例（含 3 个 AppTest；本地全量 284 含 2 个 slow）**，覆盖率门槛 55% 只在 3.12 上统计（实测 3.10 全套 88s / 3.12 含覆盖率 76s）
- AppTest「3.10 超时」根因（已定位并修复）：不是 AppTest 挂起，而是 `pytest --cov` 在 3.10 上走 `sys.settrace` 逐行追踪，把首屏「全语料抽取」的约 160 万次 Python 层 `re.finditer` 放慢约 15 倍（实测正则调用 5.8k/s；3.12 用 PEP 669 `sys.monitoring` 为 80k/s，只慢 1.3 倍）→ 首屏 14.5s 膨胀到 ~240s，正好撞 `default_timeout=240`。修复：CI 在 3.10 上不传 `--cov`（用例全跑），覆盖率门槛保留在 3.12；`tests/test_app.py` 的版本 skip 已删除
- 首屏冷启动优化：`RuleBaselineExtractor._iter_matches()` 不再「每 token 一次 `re.finditer`」，改为 `str.find` + 手工词边界（CJK token 的 pattern 本来就是 `re.escape`，ASCII token 只多「前后非字母数字」断言，步进规则与 `finditer` 对齐）→ 全语料 4582 条（v1.3.1 时口径）抽取 **24.3s → 1.5s**（同机 3.12）；`tests/test_rule_baseline.py::test_iter_matches_equivalent_to_regex_reference` 用旧正则做参照逐位置比对，全语料输出逐条一致。同时 `src/app/app.py` 把 `load_core()` 拆成「轻核心（词表 + 抽取器）」+ `load_engine()`（TF-IDF / 差距分析，才 import sklearn，本机冷导入 4.5s），默认首屏「技能图谱」不再付 sklearn 开销 → AppTest 首屏 **32s → 3.9s**（本机；仅抽优化后是 8.8s）；新增 `scripts/bench_extract.py` 复现抽取耗时
- CI 失败可见性：失败用例写入 check-run 注解 + job summary，并上传 `pytest.log` 产物（无需登录 Actions 即可用 API 查看）
- 保活：`.github/workflows/keep-streamlit-alive.yml` 每 6 小时探测（cron `17 */6 * * *`，单步运行 + 20 分钟超时 + Playwright 缓存）

## 已知问题（诚实标注）
1. BERT-NER 弱标注无法替代人工标注（已恢复旧模型 exact 0.636，弱标注版 0.545 已弃用）
2. 华为 AI 岗位数据源受限：门户已枯竭（社招2/校招0），51job 第三方 AI 岗极少
3. 阿里招聘分散在业务集团、智谱招聘渠道未公开，尚未打通
4. DeepSeek（公司）详情接口 necromancer 加密未逆向，只抓列表
5. importance 频率≠价值（如「数据标注」高频低门槛），已用难度加权修正
6. ~~`ENGINEERING.UNITTEST` 的 aliases 含泛化词「测试」~~ **已修复（迭代 6）**：改用 `skip_extract: [测试]`，JD 命中 11.37% → 0.28%（521 → 13 条），importance 5→1，gold F1 三项不变（说明原命中不是金标真值，属纯口径噪声；「量化」同类问题 6.31% → 1.07%）

## 决策演进（关键）
1. SiameseUIE 零样本对抽象技能 F1=0 → 弃用，保留「规则基线 + BERT-NER」双路
2. 匹配评测「短技能名」太简单（都 0.975）→ 升级为「口语化句子」（体现 BGE 2.25 倍优势）
3. importance 人工标定 → 数据驱动（JD 需求频率）
4. 简历解析「正则优先」→「LLM 优先、正则兜底」（LLM 完整专业名更准确）
5. 弱标注扩 BERT-NER 失败 → 结论：需人工标注更多样本
6. 本地部署 → 支持云端：依赖分层（运行/重模型拆分）、清洗数据入库、secrets 优先、sys.path 兼容
7. 学习计划「只有 LLM 能给」→「规则版常驻 + LLM 增强」：规则路径确定性、可单测、无 key 也有产出；LLM 版只做个性化补充
8. CI 从「跑一遍 pytest」→「结构校验 + 覆盖率门槛 + 版本矩阵 + 指标回归 + nightly 全量」：指标阈值写进测试（容差 1~2pt），避免改词表后静默退化
9. 报告导出放在 `st.session_state` 而不是按钮块内：Streamlit `download_button` 点击会 rerun，按钮块消失会导致下载丢失
