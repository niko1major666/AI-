# 系统模式（System Patterns）

## 系统架构（数据流）
```
数据采集          技能抽取             语义匹配           差距诊断          前端展示
raw CSV    ──▶  规则基线/BERT-NER  ──▶  TF-IDF/BGE  ──▶  打分+优先级  ──▶  Streamlit
  │                 │                    │                 │                │
jobs.jsonl      skills_long         skill_id 匹配       GapReport         3 页面
```
**关键链路**：`build_dataset` → `extractor`(rule / bert_ner) → `matcher`(tfidf / bge) → `gap_analyzer` → `app`

## 目录结构
```
src/
├── data/        schema / normalize / load / build / file_parser / resume_parser / translate /
│                job_filter / skill_stats（公司×技能矩阵）/ resume_advice（简历补强建议）
├── extractor/   rule_baseline / bert_ner / siamese_uie / base / evaluate / postprocess
├── matcher/     tfidf_matcher / bge_matcher / gap_analyzer / evaluate / base /
│                jd_requirements / job_neighbors / learning_path / job_compare /
│                job_recommender / strength_profile
├── skillkb/     loader（Taxonomy，161 技能：difficulty + importance + skip_extract）
├── crawler/     tencent / bytedance / xiaomi / xiaomi_campus / deepseek / huawei /
│                huawei_51job / kimi / minimax / util
└── app/         app.py（Streamlit 三页面）+ report_export（md/docx）
data/kb/         skill_taxonomy.yaml / learning_resources.yaml
data/gold/       评测金标准（F1 / Recall@5 / resume_sentence）
data/processed/  jobs.jsonl（清洗后入库，云端部署直接读，无需重爬）
docs/            images/（界面截图）+ metrics.md（eval_all.py 自动生成）
scripts/         eval_all / validate_kb / merge_jobs / recrawl_all / recalc_importance / eval_resume_match 等
.github/         workflows/ci.yml（矩阵+覆盖率+KB 校验）/ nightly.yml（含 slow）/ release.yml / keep-streamlit-alive.yml
.devcontainer/   devcontainer.json（容器开发环境，远程提交新增）
```

## 关键技术决策
1. **双路技能抽取**：规则基线（词表字典，F1 0.957 对词表内极稳）+ 微调 BERT-NER（能学上下文）。SiameseUIE 零样本对抽象技能 F1=0 已被弃用。
2. **双路语义匹配**：TF-IDF（char n-gram 基线）+ BGE-base-zh（语义 SOTA）。差距报告的「简历自由文本→技能」场景优先 BGE（口语化句子评测 2.25 倍于 TF-IDF）。
3. **importance 数据驱动**：行业重要度 = 4582 条 JD 需求频率分档（≥10%→5 … <1%→1），替换人工标定；优先级算法叠加学习难度加权修正「频率≠价值」偏差。语料每次扩容后跑 `scripts/recalc_importance.py` 重算，并同步更新 `tests/test_skillkb.py` 中的分档断言。
4. **LLM 增强 + 正则降级**：简历解析用 DeepSeek（`DEEPSEEK_API_KEY`），LLM 优先、正则兜底，无 key 不报错。
5. **云端部署分层**：运行依赖（requirements.txt）与重模型依赖（requirements-ml.txt）拆分；清洗数据 `data/processed/jobs.jsonl` 入库；LLM key 走 Streamlit secrets 优先、环境变量兜底；app.py 启动时把项目根目录加入 sys.path。
6. **岗位标题过滤**：只按**标题**剔除土建/施工等非 AI 岗位（黑名单 + AI 白名单保护），不做正文过滤——正文里的「桥梁」多为「业务与技术之间的桥梁」比喻（25 条真实样本验证过），按正文删会误伤真岗位。实现 `src/data/job_filter.py`，开关与词表覆盖在 `configs/dataset.yaml` 的 `cleaning.title_filter`，剔除条数计入 `build_stats.json` 的 `dropped_offtopic`。
7. **must/nice 读 JD 原文，不读全行业频率**：曾经用 `demand >= 0.4` 判硬性要求，但语料里最高需求占比只有 36.2%，判据恒为 False（P0 恒空、must_weight 失效）。现在 `src/matcher/jd_requirements.py` 三级判定：句内触发词（加分语气优先，避免「熟悉 X 优先」被判硬门槛）→ 章节标题（任职要求 / 加分项）→ 全行业占比兜底；`demand` 只用于优先级排序与说明文案。实测 57.0% 岗位可判出 ≥1 项硬性要求（1.48 项/岗）。
8. **零技能岗位必须显式兜底**：1085 条（23.7%）列表式短 JD 抽不到技能，直接出报告会出现「匹配度 0% + 已覆盖全部技能」的矛盾。`src/matcher/job_neighbors.py` 用同公司 + 标题相似岗位的技能并集代理（98.7% 可覆盖），页面标注「已用相似岗位推断」，代理结果不写入原始数据。
9. **KB 扩充按「实测占比」定 importance，并用 skip_extract 分离解析/抽取口径**：新增技能先用临时脚本在 4582 条语料上跑一遍（不落库），确认命中率与对既有技能的挤占（更长的 token 优先匹配，如「多模态大模型」→ 视觉语言模型，使「多模态」12.05%）；importance 直接按 `ratio_to_importance` 口径填，跑 `recalc_importance.py` 后应零差异。同一技能若某些写法在 JD 里噪声大（「量化」多为「可量化」），把它写进 `skip_extract`：`Taxonomy.resolve()` 仍可解析（简历输入「量化」→ 模型量化），但 `RuleBaselineExtractor._build_tokens()` 不生成对应 token。学习资源按 `skill_id` 索引，`tests/test_learning_resources.py` 锁定「id 必须存在 / 不重复 / 高频技能有资源 / url 合法」，避免前端静默丢建议。
10. **学习计划「规则常驻 + LLM 增强」**：`src/matcher/learning_path.py` 用内置先修表（52 个技能、64 条强依赖）+ 拓扑排序 + 难度→学时（2/4/8/16/24h）生成确定性三阶段路径；若先修技能落在更靠后的阶段（如 P0 的 RAG 依赖 P2 的 Embedding），自动把先修提到前面阶段，否则计划顺序不可执行；缺口外的先修只写 `prereq_note` 不新增条目。LLM 解读（`report_interpreter`）仍保留，只做个性化补充。
11. **反向匹配按「公司+标题」去重、只用已抽到技能的岗位**：`src/matcher/job_recommender.py` 用 `(company, normalize(title))` 去重（同一岗位多渠道重复导致榜单被同一 JD 占满），复用 `analyzer.must_weight/nice_weight` 与 `1 + ln tf` 计分；结果在页面用 `@st.cache_data` 按「技能 id 组合」缓存，避免每次 rerun 重扫 4472 个岗位。
12. **评测阈值写进测试 + 指标报告可 diff**：`scripts/eval_all.py` 输出无时间戳的 `docs/metrics.md`，CI 在 main 上重跑并 `git diff --exit-code` 校验「报告是否随代码更新」；`tests/test_extraction_baseline.py` / `test_matcher_baseline.py` 固化实测基线（F1 容差 1pt、Recall 容差 2pt），`test_dataset_snapshot.py` 锁定语料规模与字段，`scripts/validate_kb.py` 做结构校验（id/别名冲突/类别/难度/资源 url）。CI 分层：PR 跑 `-m "not slow"` + 覆盖率门槛，nightly 跑含全语料遍历的全量。

## 设计模式
- **接口抽象**：`Extractor.extract()`、`Matcher.fit()/search()`，便于多实现对比评测
- **dataclass 数据模型**：`JobPosting`、`SkillSpan`、`GapItem`、`GapReport`、`ResumeProfile`、`LearningPath/Stage/Step`、`ComparedJob/CompareResult`、`JobSuggestion`
- **纯函数 + 薄 UI**：`learning_path` / `job_compare` / `job_recommender` / `strength_profile` / `skill_stats` / `resume_advice` / `report_export` 都不依赖 Streamlit，页面只做取值与渲染，便于单测
- **配置化**：configs/*.yaml（dataset/extraction/matching），column_mapping 适配未知 CSV
- **缓存资源**：Streamlit `@st.cache_resource`（load_core）、`@st.cache_data`（load_jobs/extract_corpus/_resume_profile/_recommendations）
- **诚实标注**：所有实验（含失败）记录在 README / PROJECT_REPORT.md

## 组件关系
- `Taxonomy`（skillkb/loader）是核心词表，被 extractor / matcher / gap_analyzer / app 共享
- `SkillGapAnalyzer` 聚合 taxonomy + resources + matcher，产出 GapReport
- `GapReport` 的消费方：`learning_path`（学习顺序）、`report_export`（md/docx）、`app` 卡片/对比/画像
- `app.py` 的 load_core() 一次性加载 taxonomy/rule/analyzer（@st.cache_resource）

## 爬虫模式（关键实现路径）
- **Moka 平台**（DeepSeek/Kimi）：详情接口 necromancer 加密 → Playwright 渲染后 DOM 抓明文
- **飞书招聘**（字节/小米校招/MiniMax）：接口 `search/job/posts` 带 `_signature` → Playwright 拦截响应 + 搜索框交互 + 滚动懒加载
- **公开接口**（腾讯/小米社招/华为）：requests 直接调，多关键词遍历 + 限速
- 七源合并：`scripts/merge_jobs.py` → all_jobs.csv → `build_dataset` → jobs.jsonl
