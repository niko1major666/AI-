# 进度（Progress）

## 什么能用（已完成）
- ✅ 数据采集：4586 条真实 JD / 78 家公司（腾讯/字节/小米/DeepSeek/华为/Kimi/MiniMax/快手/小红书 + 英文科技岗位），含部门/发布时间等字段
- ✅ 技能抽取：规则基线（F1 0.957）+ BERT-NER（exact 0.636 / overlap 0.909，已恢复旧模型），147 技能（难度+重要度）
- ✅ 语义匹配：TF-IDF + BGE；口语化句子评测 Recall@5：BGE 0.54 vs TF-IDF 0.24
- ✅ 差距诊断：匹配度 + 缺失技能全清单 + P0/P1/P2 优先级 + 重要度（数据驱动）+ 难度 + 学习资源 + 道桥迁移
- ✅ 简历解析：正则 + DeepSeek LLM 增强（姓名/工作经历/完整专业名）+ ATS 改进建议
- ✅ 前端：Streamlit 三页面（技能图谱/简历匹配/差距报告），卡片式 UI、星级展示
- ✅ 工程：91 测试全通过（含保活脚本纯函数测试 + 小红书爬虫解析测试）、Docker、报告导出 Word、README + 项目报告
- ✅ 云端部署：依赖分层（requirements.txt 轻量 / requirements-ml.txt 重模型）、清洗数据 jobs.jsonl 入库、Streamlit secrets 支持、sys.path 兼容（Streamlit Community Cloud）
- ✅ SSH 推送：生成 ed25519 key + `~/.ssh/config` + 公钥，main 分支已同步远程（`niko1major666/AI-`）
- ✅ GitHub 发行：public 仓库 + Description/Topics + MIT License + Release v1.0.0 + GitHub Actions CI（66 测试绿）+ README 三页面截图/徽章/在线体验链接
- ✅ LLM 生成式报告解读 + 学习计划：report_interpreter（DeepSeek，LLM 优先/模板兜底），差距报告页新增「AI 解读 + 学习计划」区块
- ✅ 快手爬虫：社招（逆向 sign HMAC-SHA256）+ 校招（POST 无 sign），共 1396 条完整 JD
- ✅ DeepSeek 详情：33 条从列表升级为完整 JD（平均 1267 字）
- ✅ BERT-NER 旧模型恢复：restore_ner.py 从 bert-base-chinese 重训 30 条人工标注，exact 0.545→0.636
- ✅ 简历解析优化：工作经历细粒度（职责/量化成果/技术栈）、work_years 正则 bug 修复、LLM skills 补充技能抽取、ATS 建议增强（姓名/经历完整性/量化）
- ✅ 云端保活：GitHub Actions 每 6 小时探测（HTTP health + Playwright 真实唤醒），本地 `scripts/keepalive_app.py`，交互式 `scripts/keepalive.sh`，`.gitattributes` 保证 `.sh` 用 LF
- ✅ 小红书爬虫：`pageQueryPosition` 直连（无需签名）社招 864 + 校招 508，清洗后 1284 条完整 JD（含 jobType / publishTime），数据 3302→4586 条 / 78 家
- ✅ 技能重要度重算（4586 条语料）：147 技能中 9 升 / 34 降 / 104 不变；新分布 1:73、2:22、3:29、4:12、5:11；Top 大模型 36.2%、Python 36.0%、智能体 22.3%；同步更新 `test_skillkb` / `test_gap_analyzer` 分档断言

## 量化指标（当前）
| 项 | 值 |
|---|---|
| 数据规模 | 4586 条 / 78 家公司 |
| 技能抽取 F1 | 规则 0.957 / BERT-NER 0.636(exact) 0.909(overlap) |
| 匹配 Recall@5 | BGE 0.54 vs TF-IDF 0.24（口语化句子） |
| 测试 | 91 用例 |

## 待构建（按价值）
1. 阿里/智谱数据补充（需探查招聘渠道）
2. 简历解析继续增强（工作经历 vs 项目经历分离标注，可选）

## 当前状态
- Streamlit 运行中：http://localhost:8501
- 云端部署已就绪：Streamlit Community Cloud（secrets 填 `DEEPSEEK_API_KEY`，详见 README「云端部署」）
- DeepSeek API key 已配置到用户环境变量
- git 工作区干净（HEAD 6275aa0），main 与远程一致，tag v1.1.0 已发布（Release v1.1.0）
- CI 绿：GitHub Actions 81 测试全通过；在线体验 https://hdwqwu3howppf2z2xv9i2q.streamlit.app/
- 保活：`.github/workflows/keep-streamlit-alive.yml` 每 6 小时探测（cron `0 */6 * * *`），失败自动转 Playwright 唤醒

## 已知问题（诚实标注）
1. BERT-NER 弱标注无法替代人工标注（已恢复旧模型 exact 0.636，弱标注版 0.545 已弃用）
2. 华为 AI 岗位数据源受限：门户已枯竭（社招2/校招0），51job 第三方 AI 岗极少
3. 阿里招聘分散在业务集团、智谱招聘渠道未公开，尚未打通
4. DeepSeek（公司）详情接口 necromancer 加密未逆向，只抓列表
5. importance 频率≠价值（如「数据标注」高频低门槛），已用难度加权修正
6. `ENGINEERING.UNITTEST` 的 aliases 含泛化词「测试」→ 11.4% 命中（importance 5），高于真实水平；收紧别名会改变规则基线 F1，故暂未改动，仅记录为口径噪声

## 决策演进（关键）
1. SiameseUIE 零样本对抽象技能 F1=0 → 弃用，保留「规则基线 + BERT-NER」双路
2. 匹配评测「短技能名」太简单（都 0.975）→ 升级为「口语化句子」（体现 BGE 2.25 倍优势）
3. importance 人工标定 → 数据驱动（JD 需求频率）
4. 简历解析「正则优先」→「LLM 优先、正则兜底」（LLM 完整专业名更准确）
5. 弱标注扩 BERT-NER 失败 → 结论：需人工标注更多样本
6. 本地部署 → 支持云端：依赖分层（运行/重模型拆分）、清洗数据入库、secrets 优先、sys.path 兼容
