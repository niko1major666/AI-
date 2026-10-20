# 活跃上下文（Active Context）

## 当前工作焦点
- 刚新增「Streamlit 云端保活」：GitHub Actions 每 6 小时探测（`/~/+/_stcore/health` + Playwright 真实唤醒），本地可手动跑 `scripts/keepalive_app.py`
- 已完成「简历解析优化」：工作经历细粒度（职责/量化成果/技术栈）、work_years 正则 bug 修复、LLM skills 利用、ATS 建议增强
- BERT-NER 旧模型已恢复（exact 0.636）；快手爬虫数据 1878→3302 条
- 简历解析 DeepSeek LLM 增强已稳定（LLM 优先、正则兜底），API key 支持「Streamlit secrets 优先 + 环境变量兜底」

## 近期变更（按时间倒序）
1. Streamlit 云端保活：`scripts/keepalive_app.py`（HTTP 探测 `/~/+/_stcore/health`，失败则 Playwright 真实打开唤醒）+ `.github/workflows/keep-streamlit-alive.yml`（每 6 小时 cron + 手动触发）+ 下载社区 `scripts/keepalive.sh`（已预置应用地址）+ `.gitattributes` 强制 `.sh` 用 LF + 7 个纯函数测试
2. 简历解析优化：工作经历细粒度（职责/量化成果/技术栈）+ 修复 work_years 正则 bug（「2023 年毕业」不再误识别为 23 年经验）+ 利用 LLM skills 补充技能抽取 + ATS 建议增强（姓名/经历完整性/量化）
3. BERT-NER 旧模型恢复：restore_ner.py 从 bert-base-chinese 重训，exact 0.545→0.636 / overlap 0.909
4. 快手爬虫：社招（逆向 sign HMAC-SHA256）+ 校招（POST 无 sign），数据 1878→3302 条 / 77 家
5. DeepSeek 详情补充：33 条列表升级为完整 JD（平均 1267 字）
6. LLM 生成式报告解读 + 学习计划（report_interpreter，LLM 优先/模板兜底）+ 修复 _get_api_key 占位符 bug（环境变量优先 + 过滤占位符）
7. GitHub 发行：Release v1.0.0 + GitHub Actions CI（66 测试绿）+ 徽章 + 在线体验链接 + 分享图/宣传文案
8. README 三页面使用截图（docs/images/：技能图谱/简历匹配/差距报告）+ MIT License
9. SSH 配置 + 推送到 GitHub（ed25519 key + `~/.ssh/config` + 公钥，main 与远程一致）
10. 拉取远程「Added Dev Container Folder」提交（`.devcontainer/devcontainer.json`）
11. 云端部署 sys.path 兼容修复（streamlit run 时项目根目录不在 sys.path）
12. 云端部署准备（精简依赖 + 数据入库 + Streamlit secrets 支持）
13. 简历解析 LLM 增强（DeepSeek，验证通过）+ 合并策略 LLM 优先
14. 简历结构化解析（正则）+ ATS 改进建议
15. BERT-NER 弱标注扩充实验（诚实负面结果：exact 0.545 / overlap 0.909）
16. 匹配评测升级：口语化简历句子→技能（BGE 0.54 vs TF-IDF 0.24）
17. 技能行业重要度数据化（基于 1878 条 JD 需求频率）
18. 新增 Kimi（Moka）+ MiniMax（飞书）爬虫
19. 差距报告增加重要度/难度/优先补充建议，卡片式 UI
20. 岗位下拉显示部门+发布时间、多关键词模糊搜索、技能图谱公司筛选

## 下一步（按价值排序）
1. 观察 keep-alive 定时任务（Actions 页面确认每 6 小时跑通，必要时用 `workflow_dispatch` 手动触发）
2. 阿里/智谱数据补充（需继续探查招聘渠道）
3. 简历解析继续增强（工作经历 vs 项目经历分离标注，可选）

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
- 快手 JD 含 U+2028/2029（行/段分隔符）：json.dumps(ensure_ascii=False) 保留裸字符，splitlines() 读回误当换行符截断 JSON → build_dataset 写时显式转义 + load_jobs 改用 split("\n")
- 弱标注无法替代人工标注的边界精度（NER 细粒度任务）
- Moka 平台详情接口 necromancer 加密 → 用 Playwright DOM 抓渲染后明文
- 飞书招聘统一接口 `search/job/posts` → 拦截复用
- 华为门户已枯竭、阿里招聘分散、智谱渠道未公开（数据源客观限制）
- 简历工作年限正则需加数字前缀负向断言，否则「2023 年毕业」会被误识别为「23 年经验」
- Streamlit Community Cloud 保活：`/~/+/_stcore/health` 返回纯文本 `ok` 即实例就绪；休眠页含 "gone to sleep"/"get this app back up" 特征；单纯 HTTP GET 不建立 websocket，真正唤醒需浏览器访问（Playwright）
