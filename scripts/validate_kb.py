"""校验知识库（技能词表 + 学习资源）结构一致性。

CI 入口：`python scripts/validate_kb.py`（失败返回 1）。
也可被测试复用：`validate_repo()` 返回错误列表。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TAX_PATH = ROOT / "data" / "kb" / "skill_taxonomy.yaml"
RES_PATH = ROOT / "data" / "kb" / "learning_resources.yaml"

_ID_RE = re.compile(r"^[A-Z][A-Z0-9]*\.[A-Z0-9_]+$")
_URL_RE = re.compile(r"^https?://\S+$")


def _norm(s) -> str:
    return re.sub(r"[\s·_\-/（）()【】\[\]]+", "", str(s or "").strip().lower())


def validate_taxonomy(data: dict) -> list[str]:
    """技能词表：id/名称/别名唯一、类别存在、难度与重要度在 1~5。"""
    errors: list[str] = []
    cats = [c.get("id") for c in data.get("categories", []) or []]
    if not cats:
        errors.append("taxonomy: 缺少 categories")
    if len(cats) != len(set(cats)):
        errors.append("taxonomy: categories 存在重复 id")

    skills = data.get("skills") or []
    if not skills:
        errors.append("taxonomy: 缺少 skills")

    seen_ids: dict[str, str] = {}
    seen_names: dict[str, str] = {}
    token_owner: dict[str, str] = {}
    for s in skills:
        sid = str(s.get("id") or "")
        where = sid or "<无 id>"
        if not _ID_RE.match(sid):
            errors.append(f"taxonomy[{where}]: id 需形如 CATEGORY.NAME（大写字母/数字/下划线）")
        if sid in seen_ids:
            errors.append(f"taxonomy[{where}]: id 重复")
        seen_ids[sid] = where

        if s.get("category") not in cats:
            errors.append(f"taxonomy[{where}]: category 未在 categories 中定义")

        name = str(s.get("name") or "").strip()
        if not name:
            errors.append(f"taxonomy[{where}]: name 为空")
        elif _norm(name) in seen_names:
            errors.append(f"taxonomy[{where}]: name 与 {seen_names[_norm(name)]} 重复")
        else:
            seen_names[_norm(name)] = where

        for key in ("difficulty", "importance"):
            v = s.get(key, 3)
            if not isinstance(v, int) or not 1 <= v <= 5:
                errors.append(f"taxonomy[{where}]: {key}={v!r} 必须是 1~5 的整数")

        for token in [name] + list(s.get("aliases") or []) + list(s.get("skip_extract") or []):
            key = _norm(token)
            if not key:
                errors.append(f"taxonomy[{where}]: 存在空别名")
                continue
            owner = token_owner.get(key)
            if owner and owner != sid:
                errors.append(f"taxonomy[{where}]: 别名「{token}」与 {owner} 冲突")
            token_owner[key] = sid
    return errors


def validate_resources(data: dict, skill_ids) -> list[str]:
    """学习资源：skill_id 必须存在且不重复、items 非空、title 非空、url 合法。"""
    errors: list[str] = []
    blocks = data.get("resources")
    if not isinstance(blocks, list) or not blocks:
        return ["resources: 缺少 resources 列表"]

    seen_skill: set[str] = set()
    for block in blocks:
        sid = str(block.get("skill_id") or "")
        where = f"resources[{sid or '<无 skill_id>'}]"
        if sid not in skill_ids:
            errors.append(f"{where}: skill_id 不在技能词表中")
        if sid in seen_skill:
            errors.append(f"{where}: skill_id 重复出现")
        seen_skill.add(sid)

        items = block.get("items") or []
        if not items:
            errors.append(f"{where}: items 为空")
        seen_titles: set[str] = set()
        for it in items:
            title = str((it or {}).get("title") or "").strip()
            url = str((it or {}).get("url") or "").strip()
            if not title:
                errors.append(f"{where}: 存在空 title")
            elif title in seen_titles:
                errors.append(f"{where}: title「{title}」重复")
            seen_titles.add(title)
            if url and not _URL_RE.match(url):
                errors.append(f"{where}: 非法 url「{url}」")
    return errors


def validate_repo() -> list[str]:
    tax = yaml.safe_load(TAX_PATH.read_text(encoding="utf-8"))
    res = yaml.safe_load(RES_PATH.read_text(encoding="utf-8"))
    errors = validate_taxonomy(tax)
    errors += validate_resources(res, {s["id"] for s in tax.get("skills", [])})
    return errors


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    errors = validate_repo()
    if errors:
        print(f"❌ 知识库校验失败（{len(errors)} 个问题）：")
        for e in errors:
            print("  -", e)
        return 1
    tax = yaml.safe_load(TAX_PATH.read_text(encoding="utf-8"))
    res = yaml.safe_load(RES_PATH.read_text(encoding="utf-8"))
    print(f"✅ 知识库校验通过：{len(tax['skills'])} 个技能 / "
          f"{len(tax['categories'])} 个类别 / {len(res['resources'])} 个技能有学习资源")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
