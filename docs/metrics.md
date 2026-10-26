# 评测指标（自动生成）

> 由 `python scripts/eval_all.py` 生成；改动词表 / 抽取规则 / 匹配策略后请重跑并提交。
> 结果不含时间戳，便于在 diff 中直接看到指标变化。

## 1. 技能抽取（规则基线 RuleBaselineExtractor）

| 数据集 | 样本 | Precision | Recall | F1 (exact) | F1 (overlap) |
|---|---|---|---|---|---|
| jd_skills_gold_test.jsonl | 10 | 0.9167 | 1.0000 | 0.9565 | 0.9565 |
| jd_skills_gold_train.jsonl | 30 | 0.8913 | 0.9111 | 0.9011 | 0.9231 |
| jd_skills_gold.jsonl | 40 | 0.8966 | 0.9286 | 0.9123 | 0.9298 |

## 2. 语义匹配（TF-IDF 字符 n-gram 基线）

| 数据集 | 样本 | Recall@5 | MRR | Hit@1 |
|---|---|---|---|---|
| skill_pair_gold.jsonl | 40 | 0.9750 | 0.9229 | 0.9000 |
| resume_sentence_gold.jsonl | 50 | 0.2200 | 0.1423 | 0.1000 |

> BGE 语义模型需要本地权重，不在自动评测内；对比结果见 `python scripts/eval_resume_match.py`。

## 3. 语料与知识库覆盖

- 语料规模：**5163** 条 JD / **80** 家公司
- 零技能岗位：**1212** 条（23.5%，差距报告会用同公司相似岗位兜底）
- 技能命中：**160/161**（99.4%）
- 语料未出现：ML.FED（保留词条，属于语料缺口而非词表缺口）
- 学习资源覆盖：**106/161** 个技能（65.8%），共 118 条资源

## 4. 回归阈值（测试中固化）

| 指标 | 基线 | 允许退化 | 测试 |
|---|---|---|---|
| 抽取 F1 (test, exact) | 0.9565 | 1pt | `tests/test_extraction_baseline.py` |
| 抽取 F1 (all, exact) | 0.9123 | 1pt | `tests/test_extraction_baseline.py` |
| skill_pair Recall@5 | 0.9750 | 2pt | `tests/test_matcher_baseline.py` |
| resume_sentence Recall@5 | 0.2200 | 2pt | `tests/test_matcher_baseline.py` |

