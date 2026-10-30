# 发版流程

版本号以 **git tag** 为准；`pyproject.toml` 的 `version` 与最新 `docs/release-notes/vX.Y.Z.md` 必须与 tag 一致，由 `tests/test_release_metadata.py` 在 CI 拦截漂移。

## 1. 改版本号

```text
pyproject.toml → [project] version = "X.Y.Z"   # 与将要打的 tag（去掉 v）完全相同
```

README 不用改：顶部 Release 徽章由 shields.io 动态读取最新 Release。

## 2. 写发布说明

新增 `docs/release-notes/vX.Y.Z.md`，**首行是 `# vX.Y.Z 一句话标题`**（`release.yml` 取首行去掉 `# ` 作 Release 标题，其余行作正文）：

```markdown
# v1.4.0 一句话标题

一段话概括本次变更与「有没有行为变化」。

## 新增 / 改进 / 修复 / 性能（按需保留）
- 变更点：改了什么文件、为什么、实测数据

## 完整变更
https://github.com/niko1major666/AI-/compare/v1.3.1...v1.4.0

## 在线体验
https://hdwqwu3howppf2z2xv9i2q.streamlit.app/
```

## 3. 跑门禁

```powershell
.venv\Scripts\python.exe -m pytest -m "not slow"
.venv\Scripts\python.exe scripts\validate_kb.py
.venv\Scripts\python.exe scripts\eval_all.py; git diff --exit-code docs/metrics.md   # 指标/语义有变化时必须一并提交
.venv\Scripts\python.exe scripts\source_health.py; git diff --exit-code docs/source_health.md  # 来源/新鲜度变化时必须一并提交
```

## 4. 提交、打 tag、推送

```powershell
git add -A; git commit -m "docs: vX.Y.Z 发布说明……"
git tag -a vX.Y.Z -F msg.txt        # 附注 tag，消息写版本概要
git push origin main
git push origin vX.Y.Z              # 推 tag 触发 .github/workflows/release.yml
```

## 5. 验证

```powershell
gh release view vX.Y.Z
# 或：curl -s https://api.github.com/repos/niko1major666/AI-/releases/tags/vX.Y.Z
```

确认 `draft=false`、标题与正文符合预期；同时看 main 上 CI（`metrics` / `test (3.10)` / `test (3.12)`）全绿。

## 附：重打 tag（补丁说明写错 / 需要把后续提交并入同版本）

`release.yml` 对已存在的 Release 走 `gh release edit --draft=false`，所以允许重打：

```powershell
git tag -f -a vX.Y.Z -F msg.txt
git push -f origin vX.Y.Z
```

v1.3.1 首次发布就用过这条路径（把版本元数据对齐的提交并入同一版本）。
