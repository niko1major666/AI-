# 活跃上下文（Active Context）

## 当前工作焦点
- **迭代 3 已完成（功能扩展 C1–C7 + 评测/CI 加固 D1–D7）**：规则学习路径、报告导出（md/docx）、多岗对比、反向岗位推荐、技能画像、公司×技能矩阵、简历补强建议；抽取/匹配回归基线 + 语料快照 + 覆盖率门槛（55%）+ 3.10/3.12 矩阵 + nightly + `docs/metrics.md`；测试 131→201 全绿（v1.3.1 后 203，迭代 6 后 213；W13–W16 数据扩充后 267：265 快测 + 2 slow；迭代 7 后 284：282 快测 + 2 slow；v1.5.0 后 285：283 快测 + 2 slow）
- 迭代 2 已交付（commit `5777ff9`）：技能 147→161、学习资源 11→106、`Skill.skip_extract` 修正「量化」噪声
- 迭代 1 已交付（commit `427f271`）：must/nice 三级判定、零技能岗位代理兜底、岗位内 tf 加权、简历解析缓存
- 线上：Streamlit 云端部署 + 每 6 小时保活（`/~/+/_stcore/health` 返回 200 `ok` 为唯一就绪判据）

## 权威数字（以 `docs/metrics.md` 为准；2026-10-26 重跑 `eval_all.py` 零 diff）

- 语料 **5832 条 / 81 家公司 / 5645 个唯一「公司+标题」**（原始 6321 → 过短 7 + 非 AI 工程岗 6 + 重复 476）
- 零技能岗位 **1252 条（21.5%）**，其中 **1228 条（98.1%）** 可用同公司相似岗位代理（中位 3 项）
- 词表 **161 技能**（命中 160/161，仅「联邦学习」语料未出现）；学习资源 **106/161（65.8%）**
- 硬性要求 **60.0% 岗位 / 平均 1.80 项**（句内触发词 7340 / 章节归属 974 / 占比兜底 2191）；最高技能需求占比 **38.6%**（大模型）
- 抽取 F1 test 0.9565 / 全量 0.9123；TF-IDF Recall@5 skill_pair 0.9750 / resume_sentence 0.2200
- 测试 **285**（283 快测 + 2 slow）；覆盖率 58%（CI 门槛 55%）

## 近期变更（按时间倒序）

- **v1.5.0 已发布（2026-10-29，tag `v1.5.0`）**：把 v1.4.0 之后的 W18/W19 一并发版（`pyproject` 1.4.0→1.5.0、`docs/release-notes/v1.5.0.md`）——简历经历分类（work/internship/project/other）、岗位收藏夹（去重/上限 20/`?fav=`/JSON 导出）、Streamlit 缓存指纹修复（`086602a`/`d5b8936`）与收藏夹文案修复（`771084c`）。语料/指标保持 5832 条 / 81 家、160/161；测试 267→285（283 快测 + 2 slow）。发版后 main 与远程一致，tag 推送触发 Release 工作流。

- **收藏夹文案修复（2026-10-27）**：空收藏提示原先把 `?fav=…` 链接参数直接显示给用户（被当成乱码）；改为「收藏会保存在当前页面链接中，刷新或收藏书签都不会丢」，底部说明与按钮帮助同步去掉“链接参数”措辞；`test_app_runs_without_exception` 增加断言，收藏夹简介不得包含 `?fav`/`fav=`。提交 `771084c`，CI 绿，线上已验证新文案且无 `?fav`。
- **修复线上旧语料（2026-10-27）**：线上截图显示 4582 条 / 78 家（旧版），但页面已有迭代 7 的收藏夹 → 不是数据没构建，而是 `@st.cache_data` 缓存未随 `jobs.jsonl` 更新失效。`app.py` 新增 `_file_fingerprint()`（路径 + mtime_ns + size），给 `load_core` / `load_engine` / `load_jobs` / `extract_corpus` / `_recommendations` 的缓存加指纹参数；注意 Streamlit 会跳过下划线开头的参数，首版用 `_mtime_ns`/`_size` 时缓存键实际没变，已改为非下划线并在 `tests/test_app.py` 加缓存失效回归。测试 284→**285**；已推送 `086602a` 并线上验收 **5832 / 81**（旧版 4582 / 78），公司下拉含美团 / 滴滴 / 哔哩哔哩。

- **协作约定（2026-10-26）**：新增 `memory-bank/workingAgreements.md`，固化上下文与输出预算执行规则（单文件单次 ≤400 行 / 超过分页、命令输出过滤、里程碑落盘、新会话交接、不得为省 token 牺牲的例外），并在「重要模式与偏好」加入口，后续会话按此执行

- **迭代 7：求职闭环（经历分类 + 岗位收藏，2026-10-26）**：① 简历经历新增 `kind`（`work` / `internship` / `project` / `other`）——LLM 先判定，缺省时正则按章节标题（工作/实习/项目/教育）→ 角色关键词（实习/项目/工程师等）→ 组织关键词（公司/实验室/大学）推断，教育经历明确跳过；`ResumeProfile` 增加 `work_experiences` / `project_experiences` / `other_experiences`，简历页按类型分组展示，ATS 建议改为分别提示「缺工作/实习」与「缺项目」（全为 other 时不重复提示）。② 新增 `src/matcher/job_favorites.py`（纯函数）：按「公司 + 归一化标题」去重、上限 20、`toggle_favorite` / `remove_favorite` / `is_favorited`、`?fav=job_id,...` 编解码、按 job_id 从语料还原；`JobSuggestion` 增加 `job_id`。③ `app.py` 侧边栏新增跨页面「我的收藏」面板（列表 / 移除 / 导出 JSON），差距报告页与简历推荐 Top10 增加「⭐ 收藏该岗位」按钮，收藏写入 `st.query_params`（无后端存储，刷新/书签不丢），并给 `tests/test_app.py` 差距页补收藏回归。④ 新增 `tests/test_job_favorites.py`（9 用例）+ 经历分类/ATS 用例 + recommender job_id 用例，测试 267→**284**；语料与 `docs/metrics.md` 指标不变

- **v1.4.0 已发布（2026-10-26，tag `v1.4.0`）**：把 W11–W16 一并发版（`pyproject` 1.3.1→1.4.0、`docs/release-notes/v1.4.0.md`）。语料 4582→**5832 条 / 81 家**（哔哩哔哩 194 + 滴滴 387 + 美团 669），零技能 25.4%→**21.5%**，must 56.5%→**60.0%**（1.80 项/岗），覆盖仍 160/161，测试 203→**267**；preflight 体检工具化 + 3 个爬虫/探针并入本版。顺手修掉 README 目录结构两处过期数字（13 爬虫模块 / 14 数据源、267 用例）。发版后 main 与远程一致，tag 推送触发 Release 工作流

- **接入美团（已随 v1.4.0 发布）**：新增 `src/crawler/meituan.py`——`job.meituan.com` 是 Owl + ESM 移动端 SPA（入口 bundle 仅 7KB、无接口字符串），用 Playwright 抓 `/m/position` 的 XHR 才定位到 `official/mobile/job/getJobList`；接口**匿名公开**（无 token / 签名 / cookie），`list[]` 自带 `jobDuty` + `jobRequirement` 全文，社招 3231 条。三个坑：① 分页参数必须嵌在 `page` 对象里（PC 版同名接口收顶层 `pageNo` 且把 `pageSize` 锁死 20；移动版 `pageSize` 实测上限 1000、固定用 200，17 页抓完）；② `u_query_id` / `r_query_id` 是「本次查询」token，**整轮翻页必须复用**，每页换新会被当成新搜索、永远返回第 1 页（17 页只有 200 条唯一岗位，`totalCount` 仍是 3231）→ 爬虫按 job_id 去重并在「整页无新增」/「唯一条数 < total」时抛错；③ `jobShareType=2`（2326 条）虽免 token，但正文全空，固定用 `1`。技术类 681 条（零技能 6.0%、平均 6.7 项技能），零售 90.6% / 销售客服 97.0% / 职能 71.1% / 运营 48.1% / 产品 37.0% 零技能 → 默认只落「技术类」（`--all` 全量 3231）。体检预演全绿（零技能 21.4%、must +2.3pt），合并构建后语料 5163→5832 条 / 81 家（零技能 23.5%→21.5%，must 57.7%→60.0% / 1.80 项每岗、tf≥2 49.2%、覆盖仍 160/161）；`recalc_importance` 16 项微调（强化学习 4→5、计算机视觉 3→4、Spark 3→4、Kubernetes 4→3、GCP 3→2 等）；新增 `scripts/probe_meituan.py` + `tests/test_meituan.py`（17 用例，含 token 复用与分页失效），测试 250→267

- **接入滴滴（已随 v1.4.0 发布）**：新增 `src/crawler/didi.py`——`talent.didiglobal.com` 是 Vue SPA（入口 bundle 里没有 `/api` 字符串），用 Playwright 抓 XHR 才定位到 `recruit-portal-service/api/job/front/list`；接口**公开无鉴权**（无 token / 无签名），`items[]` 自带 `jobDuty` + `jobQualification` 全文，社招 1081 条。**`size` 上限 100**（传 200 返回 `meta.code=10039`「拦截返回」+ `data=null`，HTTP 仍 200）→ 爬虫校验业务码并对「空页但只拿到 N/total」显式抛错。全站技术类 423 条（零技能 11.8%、平均 5.3 项技能），运营 53.7% / 产品 65.6% / 安全 75.0% 零技能 → 默认只落「技术」（`--all` 全量 1081）。校招在 Moka（`/api/outer/ats-apply/website/jobs` 返回 AES 密文）未接入。体检预演全绿（零技能 23.4%、must +0.3pt），合并构建后语料 4776→5163 条 / 80 家（零技能 24.4%→23.5%，must 57.5%→57.7% / 1.69 项每岗、tf≥2 45.7%、覆盖仍 160/161）；`recalc_importance` 6 项微调（计算机视觉 4→3、特征工程 1→2、Elasticsearch 2→3、Function Calling 3→4、DeepSeek 2→1、偏好对齐 3→2）；新增 `scripts/probe_didi.py` + `tests/test_didi.py`（14 用例，含分页拦截与类别过滤），测试 236→250

- **接入哔哩哔哩（已随 v1.4.0 发布）**：新增 `src/crawler/bilibili.py`——`jobs.bilibili.com` 岗位列表 POST 需要 `X-AppKey: ops.ehr-api.auth` + `X-CSRF`，token 由 `api/auth/apply/csrf/token` **匿名**签发（无需登录/验证码），过期返回 `code=-3` 自动刷新重试一次；社招（`/api/srs/...`，87 条）+ 校招（`/api/campus/...`，117 条）共抓 877 条，响应自带 `positionDescription` 全文 JD。全站 876 条可用岗位中技术类 184（零技能 2.2%）+ AI类 20（0%），其余运营/内容/设计岗 42%~82% 零技能 → 爬虫默认只落 `技术类 + AI类`（`--all` 保留全站）。体检预演全绿（零技能 24.4%、must +1.0pt），合并构建后语料 4582→4776 条 / 79 家，零技能 25.4%→24.4%，must 56.5%→57.5%（1.66 项/岗；句内 5227 / 章节 896 / 兜底 1804），tf≥2 45.3%，技能覆盖仍 160/161；`recalc_importance` 6 项微调（Go 4→5、Scala 1→2、模型部署 1→2、思维链 2→1、Embedding 1→2、偏好对齐 2→3）；新增 `tests/test_bilibili.py`（14 用例，含 CSRF 重试与类别过滤），测试 222→236

- **数据扩充工具化（已随 v1.4.0 发布）**：新增 `scripts/preflight_new_source.py`（只读体检，~2s，FAIL→退出码 1）：模拟 `merge_jobs`/`build_dataset` 的合并与去重后，输出结构清洗、job_id 冲突、正文跨源重复（含「新源在前/在后」两种丢行数）、公司写法分裂、新源零技能率、合并后零技能占比（20%~28%）、技能覆盖（≥159）、must 占比偏移（±3pt）与自带 skills 列的词表缺口；现有语料自检精确复现当期货架口径（接入哔哩哔哩前为 4582/78/1162/160/56.5%/1.49 项每岗/句内 4830·章节 175·兜底 1804）。新增 `memory-bank/dataOnboarding.md`（SOP + 四处常量同步清单 + 五个静默坑 + 基线 + 自检清单）；新增 `tests/test_preflight_new_source.py`（9 用例），测试 213→222

- **迭代 6（已随 v1.4.0 发布）**：`ENGINEERING.UNITTEST` 收紧（`skip_extract: [测试]`）：JD 命中 521 条（11.37%）→ 13 条（0.28%），其中 508 条原本只靠裸「测试」（A/B 测试、渗透测试、性能测试、测试团队）；`recalc_importance` 5→1，gold F1 三项零变化（0.9565 / 0.9011 / 0.9123）。连带指标：零技能 1104→1162（25.4%）、代理 98.1%→97.9%（1138 条，中位 3）、must 56.8%→56.5%（1.49 项/岗；句内 4830 / 章节 175 / 兜底 1804）、tf≥2 岗位 43.9%。学习路径新增「已学进度」：`build_learning_path(..., learned=...)` 跳过已掌握技能并视为已具备先修（`path.skipped` 记录），页面差距报告改为 session 渲染（勾选即时重排、报告不再因 rerun 消失），AI 解读按「岗位+技能」缓存；测试 207→213

- **迭代 5（已随 v1.4.0 发布）**：README 界面预览新增「公司×Top12 技能矩阵」「多岗对比初始界面」两张区域截图并重写介绍；`demand_matrix` 行序改为 JD 数降序（同数量按名称），避免 1~2 条 JD 的小公司以 0%/100% 占满首屏，新增 `test_matrix_companies_sorted_by_job_count_desc`；按 `docs/metrics.md` 统一校正文档数字（零技能 1104 / 24.1%、代理 98.1% / 中位 3、must 56.8% / 1.50、PROJECT_REPORT 4582/78/161/207、techContext 8→11 源）；测试 207

1. 迭代 3（功能 + 评测/CI）：
   - 功能：`learning_path`（规则版学习路径：P0/P1/P2 三阶段、先修拓扑排序、难度→学时 2/4/8/16/24h、周数向上取整；先修若落在后续阶段自动提前并给 `prereq_note`）、`report_export`（Markdown + docx，`safe_filename` 清洗；报告写 `st.session_state` 以躲过 download_button 的 rerun）、`job_compare`（多岗匹配度/P0 数/共性缺口/独有缺口/优先投递）、`skill_stats`（公司×Top12 技能矩阵，Streamlit ProgressColumn 呈现，未引入 matplotlib）、`resume_advice`（简历原文命中 → 改写要点；未命中 → 小项目建议；数字全用 XXX 占位符）、`job_recommender`（「公司+标题」去重 + must/nice 加权 + Top10 + 最该补）、`strength_profile`（类别需求加权覆盖率 + 最大短板）
   - 页面：简历页新增技能画像 + Top10 岗位；差距页新增「分析模式」单岗/多岗切换、简历补强建议、规则学习路径、导出按钮；图谱页新增公司×Top12 技能表
   - 评测：`test_extraction_baseline`（F1 test 0.9565 / 全量 0.9123，容差 1pt）、`test_matcher_baseline`（Recall@5 0.975/0.22，容差 2pt）、`test_dataset_snapshot`（5163/80/4988；slow 用例校验 160/161 覆盖与零技能占比）、`test_validate_kb`
   - 工程：`scripts/eval_all.py` → `docs/metrics.md`（无时间戳、可 diff，CI main 校验未过期）、`scripts/validate_kb.py`、CI 覆盖率门槛 55% + 3.10/3.12 矩阵 + pip 缓存 + concurrency、`.github/workflows/nightly.yml` 跑含 slow 的全量；测试 131→201（当前 213：211 快测 + 2 slow），全量约 40s
   - 首屏冷启动优化：`rule_baseline._iter_matches()` 用 `str.find` + 手工词边界替代「每 token 一次 `re.finditer`」（全语料 4582 条 24.3s → 1.5s，逐条输出一致，`test_iter_matches_equivalent_to_regex_reference` 以旧正则作参照锁死语义）；`app.load_core()` 拆成轻核心（词表 + 抽取器）与 `load_engine()`（TF-IDF/差距分析，才 import sklearn，本机冷导入 4.5s），默认首屏不再付该开销；本机 AppTest 首屏 32s → 3.9s；`scripts/bench_extract.py` 可复现
   - 发布 v1.3.0（Release「v1.3.0 求职闭环与评测加固」，正文 `docs/release-notes/v1.3.0.md`，由 push tag 的 `release.yml` 自动创建）
   - 发布 v1.3.1（补丁：首屏冷启动 32s→3.9s、抽取 24.3s→1.5s、3.10 恢复跑全量且不再撞 240s 超时，测试 201→203；正文 `docs/release-notes/v1.3.1.md`，push tag 后由 `release.yml` 自动建 Release）
   - v1.3.1 tag 重打一次以并入「版本元数据对齐」提交：`pyproject version 0.1.0 → 1.3.1`、README 动态 Release 徽章 + 「版本与发布」章节 + W10、`docs/RELEASING.md`、`tests/test_release_metadata.py`；`release.yml` 走 `gh release edit --draft=false` 更新已存在的 Release
   - 首次推 CI 暴露三处环境依赖并已修复：① `test_dataset_snapshot` 读 `data/processed/build_stats.json`，而 `data/processed/` 在 .gitignore 里（只有 jobs.jsonl 强制入库）→ 改为「常量必校验 + stats 存在时交叉校验」；② AppTest 默认 `default_timeout=60` 不够冷启动全语料抽取 → 提到 240s；③ 3.10 runner 上首个 AppTest 240s 超时的**真因是覆盖率追踪而非 AppTest 挂起**：`pytest --cov` 在 3.10 用 `sys.settrace`，把首屏约 160 万次 Python 层 `re.finditer` 放慢约 15 倍（实测 5.8k/s；3.12 的 PEP 669 `sys.monitoring` 为 80k/s，仅慢 1.3 倍），首屏 14.5s → ~240s。修复：CI 在 3.10 上只跑用例不传 `--cov`（含 AppTest，全套 88s），覆盖率门槛保留 3.12；`tests/test_app.py` 的版本 skip 已删除。CI 失败用例现在写进 check-run 注解 + job summary（无需登录即可用 API 查看）

2. 迭代 2（KB 内容补全）：`skill_taxonomy` 147→161 —— 新增 16 项 JD 高频缺失技能（视觉语言模型 5.87%、Function Calling 4.60%、MCP 2.75%、视频生成 2.58%、扩散模型 2.36%、偏好对齐 1.70%、昇腾 1.70%、长上下文 1.16%、DeepSeek 1.05%、Qwen/Llama/GLM/世界模型/具身智能/LangGraph/Dify），合并 2 个零命中冗余项（文本向量化→Embedding、华为云→云计算）并保留别名；`learning_resources` 11→106 项（Top 80 需求技能覆盖 77）；新增 `Skill.skip_extract` 把「解析侧词表」与「抽取侧词表」分离，修正裸「量化」误匹配（6.31%→1.07%，importance 4→2，简历输入「量化」仍解析为模型量化）；实测 160/161 技能可命中（仅「联邦学习」未出现），全语料抽取 11.0s；新增 `tests/test_learning_resources.py`（6 用例）与词表/抽取回归，测试 122→131

3. 保活失败修复（实测定位）：主页在「醒着」和「休眠」时都返回同一份前端 HTML 壳（约 9.7 KB，`gone to sleep` 由 JS 渲染），原脚本 `looks_sleeping(home.text)` 恒为 False；且唤醒后只等「body 文本 > 50 字」（休眠页本身就有 193 字）→ 立即误判成功、复检 `/~/+/_stcore/health` 仍 400，于是 GitHub Actions 每 6 小时必红、应用长期休眠。改为以 health 为唯一判据（就绪 200 纯文本 `ok` / 休眠 400 空 body），Playwright 点「Yes, get this app back up!」后**轮询 health 直到 ok**（冷启动实测 262 秒、期间整页白屏），健康时也建立一次真实会话重置闲置计时；workflow 合并为单步 + `timeout-minutes: 20` + Playwright 浏览器缓存 + cron 改 `17 */6 * * *` 错峰；新增 6 个伪造响应/纯函数测试（102→108）
4. 新增岗位标题过滤器：`src/data/job_filter.py` 黑名单（土木/建筑/道路桥梁/施工/监理/结构工程师等 34 词）+ 白名单（AI/算法/大模型/数据等 31 词）保护「建筑智能化 AI」「模型结构优化」这类真 AI 岗；只按标题判、不做正文过滤（正文「桥梁」的 25 条全是「业务与技术之间的桥梁」比喻）；`configs/dataset.yaml` 增加 `cleaning.title_filter` 开关与词表覆盖，`build_dataset` 接入并输出 `dropped_offtopic` / `offtopic_samples`；重建语料 4586→4582（剔除 包装结构工程师 / 电池系统结构工程师 / 暖通工程师 / 建筑设计管理），`recalc_importance` 后 147 技能分档零变化；新增 `tests/test_job_filter.py`（7 用例）
5. 差距报告「AI 解读」改为简历专业驱动：`page_resume` 解析后写入 `st.session_state["user_majors"]`，`page_gap` 读取并透传 `interpret_report(user_majors=...)`；`report_interpreter` 新增 `_MAJOR_HINT_RULES`（计算机 / 数理统计 / 自动化电子 / 土木工程 / 经管 / 生医化 / 人文 7 类 + 通用兜底）按专业名生成迁移建议，无专业时 tips 为空且前端不展示；prompt 增加「用户专业」段并禁止编造；顺带修复差距页循环变量覆盖 `label` 导致 `target_job` 被传成「P2 可选」的 bug
6. 移除「道桥背景迁移」能力（用户反馈多为非道桥背景）：删除 `data/kb/transfer_map.yaml` + `scripts/demo_background.py`；`SkillGapAnalyzer` 去掉 `transfer_map` 参数、`detect_background()` 与 `GapItem.transfer_hint`；报告解读 prompt / 兜底模板 / 简历匹配页 / 差距报告页全部改为中性表述；同步清理 README、PROJECT_REPORT、memory-bank 与简历专业识别词表
7. 小红书爬虫 + 重要度重算：探查 job.xiaohongshu.com（SPA）→ 定位 `websiterecruit/position/pageQueryPosition`（社招/校招同接口，`x-s` 签名未强制校验）→ requests 直连翻页，社招 864 + 校招 508，清洗后 1284 条完整 JD，数据 3302→4586 条 / 78 家；新增 `tests/test_xiaohongshu.py`（10 用例）；随后按 4586 条语料重跑 `recalc_importance.py`（147 技能：9 升 34 降，Top 大模型 36.2% / Python 36.0% / 智能体 22.3%），同步 `test_skillkb` / `test_gap_analyzer` 分档断言
8. Streamlit 云端保活：`scripts/keepalive_app.py`（HTTP 探测 `/~/+/_stcore/health`，失败则 Playwright 真实打开唤醒）+ `.github/workflows/keep-streamlit-alive.yml`（每 6 小时 cron + 手动触发）+ 下载社区 `scripts/keepalive.sh`（已预置应用地址）+ `.gitattributes` 强制 `.sh` 用 LF + 7 个纯函数测试
9. 简历解析优化：工作经历细粒度（职责/量化成果/技术栈）+ 修复 work_years 正则 bug（「2023 年毕业」不再误识别为 23 年经验）+ 利用 LLM skills 补充技能抽取 + ATS 建议增强（姓名/经历完整性/量化）
10. BERT-NER 旧模型恢复：restore_ner.py 从 bert-base-chinese 重训，exact 0.545→0.636 / overlap 0.909
11. 快手爬虫：社招（逆向 sign HMAC-SHA256）+ 校招（POST 无 sign），数据 1878→3302 条 / 77 家
12. DeepSeek 详情补充：33 条列表升级为完整 JD（平均 1267 字）
13. LLM 生成式报告解读 + 学习计划（report_interpreter，LLM 优先/模板兜底）+ 修复 _get_api_key 占位符 bug（环境变量优先 + 过滤占位符）
14. GitHub 发行：Release v1.0.0 + GitHub Actions CI（66 测试绿）+ 徽章 + 在线体验链接 + 分享图/宣传文案
15. README 三页面使用截图（docs/images/：技能图谱/简历匹配/差距报告）+ MIT License
16. SSH 配置 + 推送到 GitHub（ed25519 key + `~/.ssh/config` + 公钥，main 与远程一致）
17. 拉取远程「Added Dev Container Folder」提交（`.devcontainer/devcontainer.json`）
18. 云端部署 sys.path 兼容修复（streamlit run 时项目根目录不在 sys.path）
19. 云端部署准备（精简依赖 + 数据入库 + Streamlit secrets 支持）
20. 简历解析 LLM 增强（DeepSeek，验证通过）+ 合并策略 LLM 优先
21. 简历结构化解析（正则）+ ATS 改进建议
22. BERT-NER 弱标注扩充实验（诚实负面结果：exact 0.545 / overlap 0.909）
23. 匹配评测升级：口语化简历句子→技能（BGE 0.54 vs TF-IDF 0.24）
24. 技能行业重要度数据化（基于 1878 条 JD 需求频率）
25. 新增 Kimi（Moka）+ MiniMax（飞书）爬虫
26. 差距报告增加重要度/难度/优先补充建议，卡片式 UI
27. 岗位下拉显示部门+发布时间、多关键词模糊搜索、技能图谱公司筛选
28. 迭代 1 缺陷修复：must/nice 改为 JD 原文三级判定（`src/matcher/jd_requirements.py`：句内触发词 → 章节标题 → 全行业占比兜底），修复「需求占比 ≥ 0.4 恒不成立 → P0 恒空」；零技能岗位（1085 条 / 23.7%）改用同公司相似岗位代理（`src/matcher/job_neighbors.py`，覆盖 98.7%）并在页面标注来源；匹配度加权加入岗位内 `1 + ln tf`；`rule_baseline.extract()` 单次扫描同时产出 span 与词频；简历结构化解析按文本 `st.cache_data` 缓存，DeepSeek 超时 90s→25s 并重试一次；测试 108 → 122（新增 `test_jd_requirements.py` / `test_job_neighbors.py` / AppTest 差距页交互）

## 下一步（按价值排序）
1. 阿里/智谱数据补充（需继续探查招聘渠道）；美团校招/实习走 PC 版 `jobType` 过滤（校招 196 / 实习 371，JD 齐全）待接入；滴滴校招/实习在 Moka（响应 AES 密文），可逆向密钥后补齐
2. 观察 keep-alive 任务 + nightly 全量测试（Actions 页面确认跑通，必要时 `workflow_dispatch` 手动触发）
3. 岗位订阅（邮件/站内提醒，收藏夹已交付）
4. BGE 进 CI（模型缓存化）

## 活跃决策与考量
- 简历解析：**LLM 优先、正则兜底**（LLM 更准确完整，无 key 时降级）
- API key 获取：**环境变量优先、Streamlit secrets 兜底**，并过滤占位符/非 ASCII 值（避免 `.streamlit/secrets.toml` 占位符覆盖真实 key）
- 行业重要度：**数据驱动**（JD 需求频率），而非人工标定
- 匹配：差距报告「简历自由文本→技能」场景**优先用 BGE**（有评测实证）

## 重要模式与偏好
- 双路抽取（规则基线 + BERT-NER）互补、双路匹配（TF-IDF + BGE）
- 所有实验**诚实标注**（含失败：SiameseUIE F1=0、弱标注未达预期）
- 数据/脚本/测试分离；改动后必跑 pytest + 语法检查
- **上下文/输出预算按 `memory-bank/workingAgreements.md` 执行**：单文件单次 ≤400 行（大文件分页）、命令输出先过滤、里程碑后固化记忆并优先新开会话；不为省 token 牺牲安全、测试口径与关键决策
- **Streamlit 缓存必须绑定文件指纹**：`@st.cache_data` 不感知数据文件变化，云端会「代码新版、语料旧版」；缓存键参数用 `mtime_ns`/`size`，且**不要以下划线开头**（Streamlit 跳过这类参数）

## 学习与洞察
- st.secrets 会读取本地 `.streamlit/secrets.toml` 占位符，覆盖环境变量 key → HTTP header latin-1 编码崩溃；key 获取应环境变量优先 + 过滤占位符
- CI 只装轻量依赖（requirements.txt），测试需避免触发重依赖路径（如 PDF 文字 <10 字符会回退 OCR，需要 pymupdf，CI 未装）
- 快手 JD 含 U+2028/2029（行/段分隔符）：json.dumps(ensure_ascii=False) 保留裸字符，splitlines() 读回误当换行符截断 JSON → build_dataset 写时显式转义 + load_jobs 改用 split("\n")
- 弱标注无法替代人工标注的边界精度（NER 细粒度任务）
- 词表同时用于「JD 抽取」和「用户输入解析」时，宽泛写法会放大噪声：「量化」命中 6.31% 里大量是「可量化 / 量化指标」→ 用 `Skill.skip_extract` 把两侧词表分开（解析保留、抽取剔除），比直接删别名安全（不影响 F1、不影响用户输入）
- 覆盖率不足要区分「词表缺失」与「语料未出现」：161 技能里唯一零命中的是「联邦学习」，属于后者，不应为了指标好看删掉真实技能
- Moka 平台详情接口 necromancer 加密 → 用 Playwright DOM 抓渲染后明文
- 飞书招聘统一接口 `search/job/posts` → 拦截复用
- 华为门户已枯竭、阿里招聘分散、智谱渠道未公开（数据源客观限制）
- 简历工作年限正则需加数字前缀负向断言，否则「2023 年毕业」会被误识别为「23 年经验」
- Streamlit Community Cloud 保活（实测）：`/~/+/_stcore/health` 就绪 = 200 纯文本 `ok`、**休眠 = 400 空 body**；主页在两种状态下都是同一份前端 HTML 壳，休眠文案由 JS 渲染 → 只能看渲染文本或 health；点唤醒按钮后冷启动 2~5 分钟且页面可能整页白屏，必须轮询 health 判定，不能等「页面文本长度」
- 小红书 SPA 加载 `as.xiaohongshu.com` 安全 SDK 会给业务请求注入 `x-s` 头，但其招聘 `pageQueryPosition` 接口未强制校验签到签名 → requests 直连即可；SPA 首页无岗位列表，须进 `/social/position`（导航「社会招聘」）才触发列表 XHR
- Streamlit `download_button` 点击会触发 rerun：如果把报告只在 `if st.button(...)` 块里渲染，rerun 后块消失、下载随之丢失。正确做法是把报告/导出元信息写入 `st.session_state`，在块外用 session 数据渲染下载按钮
- Streamlit 带 `key` 的 `multiselect` 在选项集合变化（如切公司）时会保留旧值并被判为无效 → 直接变成空选择；key 里带上上下文（`cmp_jobs_{company}`）可让切公司后自动回到默认选择
- 学习路径不能只按优先级分阶段：P0 技能的先修可能落在 P2 阶段（RAG ← Embedding），必须把先修整体前移，否则「照着计划学」在顺序上不成立
- 需求加权覆盖率要给零需求技能留一个极小权重（0.001）：否则「类别里只剩冷门技能」时覆盖率会被算成 100%，掩盖真实短板
