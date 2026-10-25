"""版本元数据一致性：`pyproject.toml` 的 version 必须与最新发布说明的 tag 对齐。

CI 是浅克隆、拿不到 tag，所以以「发版时一定会新增」的
`docs/release-notes/vX.Y.Z.md` 作为版本事实来源：

1. pyproject 的 version == 最大 `vX.Y.Z` 文件名（漏改版本号 → 红）；
2. 该文件的标题行必须形如 `# vX.Y.Z ...`（`release.yml` 取它作 Release 标题）；
3. 发布说明文件名只允许 `vX.Y.Z.md`（避免 `v1.4` 这类无法比较的名字）。

真实标签由 `git push origin vX.Y.Z` 产生，流程见 `docs/RELEASING.md`。
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTES_DIR = ROOT / "docs" / "release-notes"
_SEMVER = re.compile(r"^v(\d+)\.(\d+)\.(\d+)\.md$")


def _pyproject_version():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match, "pyproject.toml 里找不到 [project] version"
    return match.group(1)


def _release_notes():
    """返回按语义版本升序排列的 [(version_tuple, path), ...]。"""
    found = []
    for path in NOTES_DIR.glob("v*.md"):
        match = _SEMVER.match(path.name)
        if match:
            found.append((tuple(int(x) for x in match.groups()), path))
    return sorted(found)


def test_pyproject_version_matches_latest_release_notes():
    notes = _release_notes()
    assert notes, "docs/release-notes/ 下没有 vX.Y.Z.md"
    latest, path = notes[-1]
    expected = ".".join(str(x) for x in latest)
    assert _pyproject_version() == expected, (
        f"pyproject version={_pyproject_version()} 与最新发布说明 {path.name} 不一致；"
        "发版时两者必须同步（见 docs/RELEASING.md）"
    )


def test_latest_release_notes_title_matches_version():
    latest, path = _release_notes()[-1]
    version = ".".join(str(x) for x in latest)
    first_line = path.read_text(encoding="utf-8").splitlines()[0]
    # release.yml 靠 `# ` 前缀取标题
    assert first_line.startswith(f"# v{version} "), first_line


def test_release_notes_filenames_are_semver():
    for path in NOTES_DIR.glob("*.md"):
        assert _SEMVER.match(path.name), f"发布说明文件名需为 vX.Y.Z.md：{path.name}"
