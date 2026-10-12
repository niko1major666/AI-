# AI 岗位技能差距分析系统（ai-skill-gap）

面向**非科班（尤其传统工科）求职者**的个人项目：分析目标 AI 岗位所需技能，与自身简历对比，
输出技能差距报告与学习优先级。体现 **NLP 信息抽取 + 语义匹配 + 工程落地** 能力。

> 作者背景：吉林大学 道路桥梁与渡河工程 大四，投递 AI+ 岗位。本项目内置「道桥背景 → AI 技能」迁移映射，作为差异化亮点。

## 一、功能

1. 采集 AI 岗位 JD（Kaggle / 爬虫 / 本地 CSV，以华为等公司优先）
2. 从 JD 抽取细粒度技能实体（`分布式训练`、`向量数据库`、`Transformer` 等专有技能）
3. 用户输入简历文本/技能列表，与 JD 技能做语义匹配
4. 输出匹配度打分 + 逐项对比 + 差距报告（缺失技能/优先级/学习资源 + 道桥迁移建议）
5. Streamlit 三页面：技能图谱 / 简历匹配 / 差距报告

## 二、技术选型

| 层 | 选型 | 说明 |
|---|---|---|
| 语言 | Python **3.12** | 本机已具备，ML 生态最稳 |
| 抽取 A | SiameseUIE（ModelScope） | 零样本，第 1 周快速跑通 |
| 抽取 B | BERT-NER（transformers） | 第 3 周提精度，产出 F1 对比 |
| 匹配 A | TF-IDF（char n-gram）+ 余弦 | 中文检索基线/对照组 |
| 匹配 B | BGE-base-zh-v1.5（768 维） | 语义匹配，第 4 周接入 |
| 前端 | Streamlit | 三页面 + 图谱可视化 |
| 部署 | 本地运行，可选 Docker | 第 5 周 |

## 三、关键依赖锁（★ 必读，防 modelscope 崩）

```text
torch>=2.5,<3
transformers>=4.57,<5          # ★ ModelScope 1.x 的 siamese_uie 是 transformers 4.x 时代代码，装 5.x 会崩
sentence-transformers>=5.1,<6  # ★ 6.x 强制 transformers>=5，与上一条冲突
tokenizers>=0.22,<=0.23.0
datasets>=4.0,<=4.8.4
modelscope[framework]>=1.40
```

> 完整清单见 `requirements.txt`。运行 `scripts/check_env.py` 可体检实际安装版本 vs 锁矩阵。

## 四、目录结构

```
ai-skill-gap/
├── configs/            dataset / extraction / matching 三份 YAML
├── data/
│   ├── raw/            原始 JD（seed 样例 sample_jobs.csv 已入库）
│   ├── processed/      清洗后结构化数据（jobs.jsonl / 统计）
│   ├── gold/           人工标注金标准（算 F1 / Recall@5）
│   └── kb/             skill_taxonomy(128技能) / transfer_map(道桥迁移) / learning_resources
├── src/
│   ├── data/           schema / normalize / load / build（★ 第一步已实现并测试）
│   ├── extractor/      SiameseUIE / BERT-NER
│   ├── matcher/        TF-IDF / BGE / gap 分析
│   ├── crawler/        Playwright（可选）
│   └── app/            Streamlit
├── scripts/            setup_env.ps1 / check_env.py
├── tests/              pytest（14 用例已通过）
├── models/             模型与缓存（重资产，git 忽略）
├── requirements.txt
└── README.md
```

## 五、快速开始

```powershell
# 1) 建 Python 3.12 venv + 装依赖 + 体检（缓存全部落在项目内，不占系统盘）
powershell -ExecutionPolicy Bypass -File scripts/setup_env.ps1

# 2) 构建结构化数据集
.\.venv\Scripts\python.exe -m src.data.build_dataset --stats

# 3) 跑测试
.\.venv\Scripts\python.exe -m pytest tests -v

# 4) 技能抽取 demo（词表规则基线 + SiameseUIE 零样本）
.\.venv\Scripts\python.exe -m src.extractor.siamese_uie --demo

# 5) 差距诊断 demo（匹配度 + 缺失技能 + 道桥迁移 + 学习资源）
.\.venv\Scripts\python.exe -m src.matcher.gap_analyzer

# 6) 前端（技能图谱 / 简历匹配 / 差距报告）
.\.venv\Scripts\python.exe -m streamlit run src/app/app.py
```

## 六、环境说明（本机实测）

- 项目盘 **D:**（141 GB 空闲）；`HF_HOME / MODELSCOPE_CACHE / UV_CACHE_DIR` 全部指向项目内 `models/`，删除项目即彻底释放
- 默认 PyPI torch 为 **CPU 版**；GPU（RTX 3050 4GB）在第 4 周 benchmark 时按需切 CUDA（见下）
- 国内镜像：`HF_ENDPOINT=https://hf-mirror.com`、pip 走清华源（均实测可达）

### GPU 加速（可选，第 4 周）

```powershell
.\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu124
```

## 七、路线图

| 周 | 交付 | 验收 |
|---|---|---|
| W0 | 环境+骨架+契约+数据模块 | ✅ 14 测试通过，CLI 出 jobs.jsonl |
| W1 | SiameseUIE 抽取 + 词表规则基线 | ✅ 29 测试通过，demo 端到端跑通 |
| W2 | TF-IDF 匹配 + 差距诊断 + Streamlit MVP | ✅ 36 测试通过，三页面 AppTest 通过 |
| W3 | BERT-NER 替换，F1 对比 | ✅ 微调 bert-base-chinese，F1 0.636(exact)/0.909(overlap) vs SiameseUIE 0.000 |
| W4 | BGE 匹配，Recall@5 对比 | ✅ BGE vs TF-IDF：Recall@5 均 0.975，MRR/Hit@1 BGE 更优 |
| W5-6 | 美化 + Docker + README 量化指标 | `docker build -t ai-skill-gap .` |

## 八、量化指标（简历用）

- 采集 JD 数量 / 覆盖公司数（`build_dataset --stats`）
- 技能抽取 F1（SiameseUIE vs BERT-NER，在 `data/gold/jd_skills_gold.jsonl` 上算 span 级）
- 语义匹配 Recall@5（BGE vs TF-IDF，在 `data/gold/skill_pair_gold.jsonl` 上算）
- 单次推理延迟（`scripts/benchmark.py`，CPU/GPU 两口径）

### 已产出：技能抽取 F1 对比（测试集 10 条，span 级）

| 方法 | P | R | F1(exact) | F1(overlap) |
|---|---|---|---|---|
| 规则基线（词表字典） | 0.917 | 1.000 | 0.957 | 0.957 |
| SiameseUIE（零样本） | 0.000 | 0.000 | 0.000 | 0.000 |
| BERT-NER（微调 30 条） | 0.636 | 0.636 | 0.636 | 0.909 |

> 结论：SiameseUIE 零样本对抽象技能类别召回为 0（已实测），微调 BERT-NER 显著提升（0→0.64/0.91）；
> 词表规则基线对「词表内技能」最稳（0.96），但无法发现词表外新技能——两者互补，正是保留双路抽取的原因。

### 已产出：语义匹配 Recall@5 对比（40 条口语表述→技能，语料 128 技能）

| 方法 | Recall@5 | MRR | Hit@1 |
|---|---|---|---|
| TF-IDF（char 2-4 gram） | 0.975 | 0.933 | 0.900 |
| BGE-base-zh-v1.5 | 0.975 | 0.944 | 0.925 |

> 结论：短技能名匹配任务上两者 Recall@5 相当（都接近满分），但 BGE 排序精度更高
> （MRR +0.011、Hit@1 +0.025）；BGE 的真正优势在长句/口语化表述的语义匹配（子句级匹配），
> 这也是差距报告中"简历自由文本 → 技能"场景应优先用 BGE 的原因。

## 九、尚未核实（诚实标注）

1. Kaggle「AI Jobs Dataset 2026」是否真实存在及其字段——数据层已做 YAML 列映射适配，任意 JD CSV 即插即用
2. `Nucha_SkillNER_BERT` 是否可获取——NER 模型名走配置，拿不到则退 `bert-base-chinese` 自标注微调
3. SiameseUIE 在本机 transformers 4.57 下的实际推理表现——装完用 `--demo` 验证
