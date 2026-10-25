# 技术上下文（Tech Context）

## 技术栈
- **语言**：Python 3.12
- **技能抽取**：规则基线（词表字典）+ BERT-NER（transformers 微调 bert-base-chinese）
- **语义匹配**：TF-IDF（char n-gram）+ BGE-base-zh-v1.5（sentence-transformers）
- **简历解析**：正则 + DeepSeek LLM（`requests` 直调 chat/completions，兼容 OpenAI 接口）
- **前端**：Streamlit + pyvis（图谱可视化）
- **爬虫**：requests + Playwright（chromium headless）
- **工程**：pytest（207 用例 = 205 快测 + 2 slow）、Docker、yaml 配置化、pandas

## 开发设置
- 项目根目录：`D:\ai-skill-gap`
- 虚拟环境：`.venv\Scripts\python.exe`
- 模型缓存：`models/hf_cache`（HF_HOME）、`models/ms_cache`（ModelScope）
- 环境变量：`DEEPSEEK_API_KEY`（用户级，简历 LLM 解析）
- 云端密钥：Streamlit Cloud Settings → Secrets 填 `DEEPSEEK_API_KEY`（模板 `.streamlit/secrets.toml`，真实 key 不入 git）
- SSH 免密推送：`~/.ssh/id_ed25519` + `~/.ssh/config`（github.com 走该 key）；远程 `git@github.com:niko1major666/AI-.git`
- 启动前端：`python -m streamlit run src/app/app.py`（端口 8501）
- 在线体验：https://hdwqwu3howppf2z2xv9i2q.streamlit.app/（Streamlit Cloud 已部署）
- CI：`.github/workflows/ci.yml`（push/PR 跑 `requirements.txt` 轻量依赖 + pytest，207 测试；3.10 只跑用例、3.12 加覆盖率门槛）

## 技术约束（★ 关键，防崩）
- **版本锁**：`transformers<5`、`sentence-transformers<6`（ModelScope 1.x 的 siamese_uie 是 transformers 4.x 时代代码，装 5.x 会崩）
- **基础模型已在缓存**：`bert-base-chinese` 在 `models/hf_cache/models--bert-base-chinese/snapshots/`（restore_ner.py 直接读 snapshot 路径，避免 HF 联网）
- **CPU 推理**：GPU（RTX 3050 4GB）可选，默认 CPU
- **国内镜像**：`HF_ENDPOINT=https://hf-mirror.com`
- **Windows**：无 symlink（HF 缓存降级警告无害）；PowerShell 环境

## 依赖要点
- 依赖分层：`requirements.txt`（轻量运行依赖，云端部署用）；`requirements-ml.txt`（重模型依赖 BERT-NER/BGE/SiameseUIE，本地 `pip install -r requirements.txt -r requirements-ml.txt`）
- `scripts/check_env.py` 体检版本
- PDF 解析：pypdf + pymupdf（渲染）+ rapidocr_onnxruntime（OCR 兜底）

## 工具使用模式
- 跑测试：`.\.venv\Scripts\python.exe -m pytest -q`
- 重爬：`python scripts/recrawl_all.py`（11 源，约 20+ 分钟）
- 合并+构建：`merge_jobs.py` → `python -m src.data.build_dataset --stats`
- 重要度重算：`python scripts/recalc_importance.py`
- 匹配评测：`python scripts/eval_resume_match.py`（需 BGE 缓存）
- 报告导出 Word：`python scripts/export_report_docx.py`
- git 提交需内联身份：`git -c user.name='QWB20' -c user.email='qwb20@example.com' commit`
- git 推送/拉取：SSH 免密（`git push` 直接可用，无需凭证）
- 云端部署：推 GitHub → Streamlit Cloud 新建 app → Main file `src/app/app.py` → Secrets 填 `DEEPSEEK_API_KEY` → Deploy（详见 README「云端部署」）
- 发 Release：GitHub Releases → Draft a new release → 打 tag（如 v1.1.0）→ 填更新说明（也可用 API `POST /repos/{owner}/{repo}/releases`）
- 快手爬虫：`python -m src.crawler.kuaishou`（社招 sign 逆向 + 校招 POST，约 1445 条）
- 恢复 BERT-NER：`python scripts/restore_ner.py 3`（从 bert-base-chinese 重训 30 条人工标注）
