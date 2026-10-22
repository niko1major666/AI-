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


def test_health_path_is_cloud_prefixed():
    """休眠时 /_stcore/health 会落到静态路由返回 HTML 壳，必须带 /~/+/ 前缀。"""
    assert keepalive.HEALTH_PATH == "/~/+/_stcore/health"


def test_looks_healthy_rejects_html_shell():
    """主页/静态路由返回 200 + HTML 时不能当作就绪。"""
    html = "<!doctype html><html><body><div id='root'></div></body></html>"
    assert keepalive.looks_healthy(200, html) is False


class _FakeResp:
    def __init__(self, status, text, content_type="text/plain; charset=utf-8"):
        self.status_code = status
        self.text = text
        self.headers = {"content-type": content_type}


def test_probe_http_awake(monkeypatch):
    monkeypatch.setattr(keepalive.requests, "get", lambda *a, **k: _FakeResp(200, "ok"))
    info = keepalive.probe_http("https://example.streamlit.app/", timeout=5)
    assert info["healthy"] is True
    assert info["status"] == 200


def test_probe_http_sleeping(monkeypatch):
    """休眠态：网关返回 400 空 body（实测行为）。"""
    monkeypatch.setattr(
        keepalive.requests, "get", lambda *a, **k: _FakeResp(400, "", "text/html")
    )
    info = keepalive.probe_http("https://example.streamlit.app/", timeout=5)
    assert info["healthy"] is False
    assert info["status"] == 400


def test_probe_http_network_error(monkeypatch):
    def boom(*_a, **_k):
        raise keepalive.requests.RequestException("timeout")

    monkeypatch.setattr(keepalive.requests, "get", boom)
    info = keepalive.probe_http("https://example.streamlit.app/", timeout=5)
    assert info["healthy"] is False
    assert "timeout" in info["error"]


def test_probe_http_hits_cloud_health_path(monkeypatch):
    seen = {}

    def fake_get(url, timeout=None, **_k):
        seen["url"] = url
        return _FakeResp(200, "ok")

    monkeypatch.setattr(keepalive.requests, "get", fake_get)
    keepalive.probe_http("https://example.streamlit.app/", timeout=5)
    assert seen["url"] == "https://example.streamlit.app/~/+/_stcore/health"

