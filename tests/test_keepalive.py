"""保活脚本的纯函数测试（不触网）。"""
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "keepalive_app.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("keepalive_app", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


keepalive = _load_module()


@pytest.mark.parametrize(
    "html",
    [
        "This app has gone to sleep due to inactivity.",
        "Yes, get this app back up!",
        "<div class='zzz'>sleeping</div>",
    ],
)
def test_looks_sleeping_true(html):
    assert keepalive.looks_sleeping(html) is True


@pytest.mark.parametrize(
    "html",
    [
        "",
        "<html><body>AI 岗位技能差距分析系统</body></html>",
    ],
)
def test_looks_sleeping_false(html):
    assert keepalive.looks_sleeping(html) is False


def test_looks_healthy():
    assert keepalive.looks_healthy(200, "ok") is True
    assert keepalive.looks_healthy(200, "OK") is True
    assert keepalive.looks_healthy(503, "ok") is False
    assert keepalive.looks_healthy(200, "") is False


def test_default_url():
    assert keepalive.DEFAULT_URL.startswith("https://")
    assert keepalive.HEALTH_PATH.endswith("/_stcore/health")
