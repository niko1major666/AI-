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
├── data/        schema / normalize / load / build / file_parser / resume_parser / translate
├── extractor/   rule_baseline / bert_ner / siamese_uie / base / evaluate / postprocess
├── matcher/     tfidf_matcher / bge_matcher / gap_analyzer / evaluate / base
├── skillkb/     loader（Taxonomy，147 技能：difficulty + importance）
├── crawler/     tencent / bytedance / xiaomi / xiaomi_campus / deepseek / huawei /
│                huawei_51job / kimi / minimax / util
└── app/         app.py（Streamlit 三页面）
data/kb/         skill_taxonomy.yaml / transfer_map.yaml / learning_resources.yaml
data/gold/       评测金标准（F1 / Recall@5 / resume_sentence）
data/processed/  jobs.jsonl（清洗后入库，云端部署直接读，无需重爬）
scripts/         merge_jobs / recrawl_all / recalc_importance / eval_resume_match / 等
```

## 关键技术决策
1. **双路技能抽取**：规则基线（词表字典，F1 0.957 对词表内极稳）+ 微调 BERT-NER（能学上下文）。SiameseUIE 零样本对抽象技能 F1=0 已被弃用。
2. **双路语义匹配**：TF-IDF（char n-gram 基线）+ BGE-base-zh（语义 SOTA）。差距报告的「简历自由文本→技能」场景优先 BGE（口语化句子评测 2.25 倍于 TF-IDF）。
3. **importance 数据驱动**：行业重要度 = 1878 条 JD 需求频率分档（≥10%→5 … <1%→1），替换人工标定；优先级算法叠加学习难度加权修正「频率≠价值」偏差。
4. **LLM 增强 + 正则降级**：简历解析用 DeepSeek（`DEEPSEEK_API_KEY`），LLM 优先、正则兜底，无 key 不报错。
5. **云端部署分层**：运行依赖（requirements.txt）与重模型依赖（requirements-ml.txt）拆分；清洗数据 `data/processed/jobs.jsonl` 入库；LLM key 走 Streamlit secrets 优先、环境变量兜底；app.py 启动时把项目根目录加入 sys.path。

## 设计模式
- **接口抽象**：`Extractor.extract()`、`Matcher.fit()/search()`，便于多实现对比评测
- **dataclass 数据模型**：`JobPosting`、`SkillSpan`、`GapItem`、`GapReport`、`ResumeProfile`
- **配置化**：configs/*.yaml（dataset/extraction/matching），column_mapping 适配未知 CSV
- **缓存资源**：Streamlit `@st.cache_resource`（load_core）、`@st.cache_data`（load_jobs/extract_corpus）
- **诚实标注**：所有实验（含失败）记录在 README / PROJECT_REPORT.md

## 组件关系
- `Taxonomy`（skillkb/loader）是核心词表，被 extractor / matcher / gap_analyzer / app 共享
- `SkillGapAnalyzer` 聚合 taxonomy + transfer_map + resources + matcher，产出 GapReport
- `app.py` 的 load_core() 一次性加载 taxonomy/rule/analyzer（@st.cache_resource）

## 爬虫模式（关键实现路径）
- **Moka 平台**（DeepSeek/Kimi）：详情接口 necromancer 加密 → Playwright 渲染后 DOM 抓明文
- **飞书招聘**（字节/小米校招/MiniMax）：接口 `search/job/posts` 带 `_signature` → Playwright 拦截响应 + 搜索框交互 + 滚动懒加载
- **公开接口**（腾讯/小米社招/华为）：requests 直接调，多关键词遍历 + 限速
- 七源合并：`scripts/merge_jobs.py` → all_jobs.csv → `build_dataset` → jobs.jsonl
