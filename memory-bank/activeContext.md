# 活跃上下文（Active Context）

## 当前工作焦点
- 刚完成「BERT-NER 旧模型恢复 + 数据补充」：restore_ner.py 恢复 exact 0.636；快手爬虫（社招+校招）sign 逆向，数据 1878→3302 条
- 简历解析 DeepSeek LLM 增强已稳定（LLM 优先、正则兜底），API key 支持「Streamlit secrets 优先 + 环境变量兜底」

## 近期变更（按时间倒序）
1. BERT-NER 旧模型恢复：restore_ner.py 从 bert-base-chinese 重训，exact 0.545→0.636 / overlap 0.909
2. 快手爬虫：社招（逆向 sign HMAC-SHA256）+ 校招（POST 无 sign），数据 1878→3302 条 / 77 家
3. DeepSeek 详情补充：33 条列表升级为完整 JD（平均 1267 字）
4. LLM 生成式报告解读 + 学习计划（report_interpreter，LLM 优先/模板兜底）+ 修复 _get_api_key 占位符 bug（环境变量优先 + 过滤占位符）
5. GitHub 发行：Release v1.0.0 + GitHub Actions CI（66 测试绿）+ 徽章 + 在线体验链接 + 分享图/宣传文案
6. README 三页面使用截图（docs/images/：技能图谱/简历匹配/差距报告）+ MIT License
7. SSH 配置 + 推送到 GitHub（ed25519 key + `~/.ssh/config` + 公钥，main 与远程一致）
8. 拉取远程「Added Dev Container Folder」提交（`.devcontainer/devcontainer.json`）
9. 云端部署 sys.path 兼容修复（streamlit run 时项目根目录不在 sys.path）
10. 云端部署准备（精简依赖 + 数据入库 + Streamlit secrets 支持）
11. 简历解析 LLM 增强（DeepSeek，验证通过）+ 合并策略 LLM 优先
12. 简历结构化解析（正则）+ ATS 改进建议
13. BERT-NER 弱标注扩充实验（诚实负面结果：exact 0.545 / overlap 0.909）
14. 匹配评测升级：口语化简历句子→技能（BGE 0.54 vs TF-IDF 0.24）
15. 技能行业重要度数据化（基于 1878 条 JD 需求频率）
16. 新增 Kimi（Moka）+ MiniMax（飞书）爬虫
17. 差距报告增加重要度/难度/优先补充建议，卡片式 UI
18. 岗位下拉显示部门+发布时间、多关键词模糊搜索、技能图谱公司筛选

## 下一步（按价值排序）
1. 阿里/智谱数据补充（需继续探查招聘渠道）
2. 简历结构化解析的进一步优化（工作经历更细粒度）

## 活跃决策与考量
- 简历解析：**LLM 优先、正则兜底**（LLM 更准确完整，无 key 时降级）
- API key 获取：**环境变量优先、Streamlit secrets 兜底**，并过滤占位符/非 ASCII 值（避免 `.streamlit/secrets.toml` 占位符覆盖真实 key）
- 行业重要度：**数据驱动**（JD 需求频率），而非人工标定
- 匹配：差距报告「简历自由文本→技能」场景**优先用 BGE**（有评测实证）

## 重要模式与偏好
- 双路抽取（规则基线 + BERT-NER）互补、双路匹配（TF-IDF + BGE）
- 所有实验**诚实标注**（含失败：SiameseUIE F1=0、弱标注未达预期）
- 数据/脚本/测试分离；改动后必跑 pytest + 语法检查

## 学习与洞察
- st.secrets 会读取本地 `.streamlit/secrets.toml` 占位符，覆盖环境变量 key → HTTP header latin-1 编码崩溃；key 获取应环境变量优先 + 过滤占位符
- CI 只装轻量依赖（requirements.txt），测试需避免触发重依赖路径（如 PDF 文字 <10 字符会回退 OCR，需要 pymupdf，CI 未装）
- 弱标注无法替代人工标注的边界精度（NER 细粒度任务）
- Moka 平台详情接口 necromancer 加密 → 用 Playwright DOM 抓渲染后明文
- 飞书招聘统一接口 `search/job/posts` → 拦截复用
- 华为门户已枯竭、阿里招聘分散、智谱渠道未公开（数据源客观限制）
