# 进度（Progress）

## 什么能用（已完成）
- ✅ 数据采集：1878 条真实 JD / 76 家公司（腾讯/字节/小米/DeepSeek/华为/Kimi/MiniMax + 英文科技岗位），含部门/发布时间等字段
- ✅ 技能抽取：规则基线（F1 0.957）+ BERT-NER（exact 0.545 / overlap 0.909），147 技能（难度+重要度）
- ✅ 语义匹配：TF-IDF + BGE；口语化句子评测 Recall@5：BGE 0.54 vs TF-IDF 0.24
- ✅ 差距诊断：匹配度 + 缺失技能全清单 + P0/P1/P2 优先级 + 重要度（数据驱动）+ 难度 + 学习资源 + 道桥迁移
- ✅ 简历解析：正则 + DeepSeek LLM 增强（姓名/工作经历/完整专业名）+ ATS 改进建议
- ✅ 前端：Streamlit 三页面（技能图谱/简历匹配/差距报告），卡片式 UI、星级展示
- ✅ 工程：66 测试全通过、Docker、报告导出 Word、README + 项目报告
- ✅ 云端部署：依赖分层（requirements.txt 轻量 / requirements-ml.txt 重模型）、清洗数据 jobs.jsonl 入库、Streamlit secrets 支持、sys.path 兼容（Streamlit Community Cloud）

## 量化指标（当前）
| 项 | 值 |
|---|---|
| 数据规模 | 1878 条 / 76 家公司 |
| 技能抽取 F1 | 规则 0.957 / BERT-NER 0.545(exact) 0.909(overlap) |
| 匹配 Recall@5 | BGE 0.54 vs TF-IDF 0.24（口语化句子） |
| 测试 | 66 用例 |

## 待构建（按价值）
1. LLM 生成式报告解读 + 学习计划（最高价值，已有 DeepSeek key）
2. 阿里/智谱数据补充（需探查招聘渠道）
3. 恢复 BERT-NER 旧模型（exact 0.636，需联网重下 bert-base-chinese）
4. 简历结构化解析的进一步优化（工作经历更细粒度）

## 当前状态
- Streamlit 运行中：http://localhost:8501
- 云端部署已就绪：Streamlit Community Cloud（secrets 填 `DEEPSEEK_API_KEY`，详见 README「云端部署」）
- DeepSeek API key 已配置到用户环境变量
- git 工作区干净（HEAD 874af44，云端部署已同步进 Memory Bank）

## 已知问题（诚实标注）
1. BERT-NER 弱标注扩充未达预期：exact 0.636→0.545（略降）、overlap 持平，弱标注无法替代人工标注
2. 华为 AI 岗位数据源受限：门户已枯竭（社招2/校招0），51job 第三方 AI 岗极少
3. 阿里招聘分散在业务集团、智谱招聘渠道未公开，尚未打通
4. DeepSeek（公司）详情接口 necromancer 加密未逆向，只抓列表
5. importance 频率≠价值（如「数据标注」高频低门槛），已用难度加权修正

## 决策演进（关键）
1. SiameseUIE 零样本对抽象技能 F1=0 → 弃用，保留「规则基线 + BERT-NER」双路
2. 匹配评测「短技能名」太简单（都 0.975）→ 升级为「口语化句子」（体现 BGE 2.25 倍优势）
3. importance 人工标定 → 数据驱动（JD 需求频率）
4. 简历解析「正则优先」→「LLM 优先、正则兜底」（LLM 完整专业名更准确）
5. 弱标注扩 BERT-NER 失败 → 结论：需人工标注更多样本
6. 本地部署 → 支持云端：依赖分层（运行/重模型拆分）、清洗数据入库、secrets 优先、sys.path 兼容
