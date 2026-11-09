"""排除清单的读取回归（语料清洗的可复现性依赖它）。"""

from pathlib import Path

from scripts.merge_jobs import load_exclusions


def test_missing_file_returns_empty(tmp_path: Path):
    assert load_exclusions(tmp_path / "nope.txt") == set()


def test_parses_ids_and_skips_comments(tmp_path: Path):
    p = tmp_path / "exclude.txt"
    p.write_text("# 说明行\nabc123\n\n  def456  \n# 另一条注释\nghi789\n", encoding="utf-8")
    assert load_exclusions(p) == {"abc123", "def456", "ghi789"}
