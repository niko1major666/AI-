"""脚本路径回归：`scripts/` 下的分析脚本不得硬编码本机绝对路径。

校验三件事：
1. 源码中不出现本机绝对路径（D 盘 + 项目目录名，正/反斜杠两种写法）；
2. `ROOT` 由 `__file__` 推导，求值后等于本仓库根（conftest.py 所在目录）；
3. 换一个 checkout 路径时，同一表达式指向该 checkout 自己的根。

只做静态检查 + 单行表达式求值，**不 import 脚本本身**，
避免触发 `datasets` / `huggingface` 等重依赖。
"""
import ast
import pathlib
import re

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ("analyze_skills.py", "verify_real.py")
_HARDCODED = re.compile(r"D:[\\/]{1,2}ai-skill-gap", re.IGNORECASE)


def _source(name):
    return (REPO_ROOT / "scripts" / name).read_text(encoding="utf-8")


def _root_expr(name):
    """取模块顶层的 `ROOT = ...` 赋值表达式。"""
    tree = ast.parse(_source(name), filename=name)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "ROOT" for t in node.targets
        ):
            return node.value
    raise AssertionError(f"{name}: 找不到顶层 ROOT 赋值")


def _eval_root(expr, script_path):
    """把 ROOT 表达式单独编译求值，只绑定 `Path` 与 `__file__`。"""
    code = compile(
        ast.fix_missing_locations(ast.Expression(body=expr)),
        filename=str(script_path), mode="eval",
    )
    return eval(code, {"Path": pathlib.Path, "__file__": str(script_path)})


@pytest.mark.parametrize("name", SCRIPTS)
def test_no_hardcoded_repo_path(name):
    """正则同时覆盖正斜杠与反斜杠写法，避免只改其中一种。"""
    source = _source(name)
    match = _HARDCODED.search(source)
    assert not match, f"{name} 仍硬编码本机绝对路径：{match.group(0)!r}"


@pytest.mark.parametrize("name", SCRIPTS)
def test_root_is_derived_from_dunder_file(name):
    expr = _root_expr(name)
    names = {n.id for n in ast.walk(expr) if isinstance(n, ast.Name)}
    assert {"Path", "__file__"} <= names, f"{name}: ROOT 必须基于 __file__ 推导"
    assert (REPO_ROOT / "conftest.py").is_file()
    assert _eval_root(expr, REPO_ROOT / "scripts" / name).resolve() == REPO_ROOT


@pytest.mark.parametrize("name", SCRIPTS)
def test_root_follows_relocated_checkout(tmp_path, name):
    """把脚本放到另一个 checkout 路径下，ROOT 应指向那个 checkout 的根。"""
    relocated = tmp_path / "another-checkout"
    script = relocated / "scripts" / name
    script.parent.mkdir(parents=True)
    script.write_text(_source(name), encoding="utf-8")

    root = _eval_root(_root_expr(name), script).resolve()
    assert root == relocated.resolve()
    assert root != REPO_ROOT


@pytest.mark.parametrize("name", SCRIPTS)
def test_sys_path_inserted_before_src_imports(name):
    source = _source(name)
    insert_at = source.find("sys.path.insert(0, str(ROOT))")
    src_imports = [i for i in (source.find("from src."), source.find("import src.")) if i != -1]
    assert insert_at != -1, f"{name}: 缺少 sys.path.insert(0, str(ROOT))"
    assert src_imports, f"{name}: 未 import src.*"
    assert insert_at < min(src_imports), f"{name}: sys.path.insert 必须在 import src.* 之前"
