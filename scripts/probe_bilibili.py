"""侦察 jobs.bilibili.com 的公开接口（只读，临时脚本）。

用法：
  python scripts/probe_bilibili.py            # 轮流试候选接口
  python scripts/probe_bilibili.py --js       # 额外列出 bundle 里的 api 路径
  python scripts/probe_bilibili.py --call     # 打印 positionList 调用点上下文
  python scripts/probe_bilibili.py --try      # 用若干 body/参数组合实打接口
  python scripts/probe_bilibili.py --sess     # 走一遍拿 ajSessionId 的流程
"""
from __future__ import annotations

import re
import sys
from urllib.parse import urljoin

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
BASE = "https://jobs.bilibili.com"
HEADERS = {"User-Agent": UA, "Referer": BASE + "/", "Origin": BASE,
           "Accept": "application/json, text/plain, */*"}

CANDIDATES = [
    "/api/srs/position/positionList",
    "/api/campus/position/positionList",
    "/api/rts/position/query/list",
    "/api/rts/position/query",
]

KEYS = ("positionList", "srs/position", "rts/position", "pageSize")


def _js_files() -> dict[str, str]:
    """app.js 里带着 chunk 映射，把能拿到的 JS 都下载下来。"""
    html = requests.get(BASE + "/", headers=HEADERS, timeout=20).text
    srcs = set(re.findall(r'"[^"]+\.js"', html))
    srcs = {s.strip('"') for s in srcs}
    app = requests.get(BASE + "/assets/js/app.js", headers=HEADERS, timeout=30)
    if app.ok:
        srcs |= set(re.findall(r'(?:assets/js/)?(chunk-[0-9a-z]+|app|position|record|resume)\.[0-9a-f]{8}\.js',
                               app.text))
    files = {}
    for src in sorted(srcs):
        url = src if src.startswith("http") else urljoin(BASE + "/assets/js/", src)
        if not url.startswith("http"):
            url = "https:" + url
        try:
            files[url] = requests.get(url, headers=HEADERS, timeout=30).text
        except Exception as exc:  # noqa: BLE001
            print(f"[ERR] {url} -> {exc}")
    return files


def probe_js() -> None:
    for url, js in _js_files().items():
        print(f"== {url} ({len(js)} chars)")
        seen = set()
        for m in re.finditer(r'["\'](/?(?:api/[^"\']{0,70}))["\']', js):
            path = m.group(1)
            if path not in seen:
                seen.add(path)
                print(f"  {path}")


def probe_calls() -> None:
    for url, js in _js_files().items():
        for key in KEYS:
            for m in re.finditer(re.escape(key), js):
                s = max(0, m.start() - 260)
                window = js[s:m.start() + 320]
                print(f"\n--- {url.split('/')[-1]} @ {key} ---\n{window}")


def probe_try() -> None:
    bodies = [
        {"pageNum": 1, "pageSize": 5},
        {"pageNum": 1, "pageSize": 5, "keyword": ""},
        {"pageNum": 1, "pageSize": 5, "positionName": ""},
        {"pageNum": 1, "pageSize": 5, "searchType": "1"},
        {"pageNum": 1, "pageSize": 5, "recruitType": "social"},
    ]
    for path in CANDIDATES:
        url = BASE + path
        for method in ("post", "get"):
            for body in bodies:
                try:
                    if method == "post":
                        r = requests.post(url, json=body, headers=HEADERS, timeout=15)
                    else:
                        r = requests.get(url, params=body, headers=HEADERS, timeout=15)
                    txt = r.text[:200].replace("\n", " ")
                    if r.status_code != 404:
                        print(f"[{r.status_code}] {method.upper()} {path} {list(body)} -> {txt}")
                    if r.status_code == 200:
                        break
                except Exception as exc:  # noqa: BLE001
                    print(f"[ERR] {method} {path} -> {exc}")


def probe_session() -> None:
    """ajSessionId 从哪来：X-AppKey + csrf/token 换 cookie，再带 cookie 打接口。"""
    s = requests.Session()
    s.headers.update(HEADERS)
    s.headers.update({"X-AppKey": "ops.ehr-api.auth", "X-UserType": "2"})
    r = s.get(BASE + "/", timeout=20)
    print(f"GET / -> {r.status_code}, cookies={dict(s.cookies)}")
    for path, method in (("/api/auth/v1/csrf/token", "get"),
                         ("/api/auth/v1/csrf/token", "post"),
                         ("/api/x/web-interface/nav", "get")):
        try:
            got = getattr(s, method)(BASE + path, timeout=15)
            print(f"{method.upper()} {path} -> {got.status_code} {got.text[:300]}")
        except Exception as exc:  # noqa: BLE001
            print(f"[ERR] {path} -> {exc}")
    print(f"cookies now={dict(s.cookies)}")
    for path in ("/social/position", "/campus/position"):
        try:
            got = s.get(BASE + path, timeout=20)
            print(f"GET {path} -> {got.status_code}, cookies={dict(s.cookies)}")
        except Exception as exc:  # noqa: BLE001
            print(f"[ERR] {path} -> {exc}")
    for body in ({"pageNum": 1, "pageSize": 3},
                 {"pageNum": 1, "pageSize": 3, "positionName": ""},
                 {"pageNum": 1, "pageSize": 3, "recruitType": "social"}):
        for method in ("post", "get"):
            try:
                if method == "post":
                    got = s.post(BASE + "/api/srs/position/positionList", json=body, timeout=15)
                else:
                    got = s.get(BASE + "/api/srs/position/positionList", params=body, timeout=15)
                print(f"[{got.status_code}] {method.upper()} srs/positionList {list(body)} -> {got.text[:300]}")
            except Exception as exc:  # noqa: BLE001
                print(f"[ERR] {method} -> {exc}")


def probe_keys(*keys: str, span: int = 420) -> None:
    """打印指定字符串在 bundle 里的上下文（找请求头/签名生成逻辑）。"""
    for url, js in _js_files().items():
        name = url.split("/")[-1]
        for key in keys:
            hits = list(re.finditer(re.escape(key), js))
            print(f"\n########## {name} @ {key} × {len(hits)}")
            for m in hits[:6]:
                s = max(0, m.start() - span)
                print(f"--- offset {m.start()} ---\n{js[s:m.start() + span]}")


def probe_csrf(token: str | None = None) -> None:
    """csrf token 拿到后怎么带：遍历常见 header / cookie 名。"""
    s = requests.Session()
    s.headers.update(HEADERS)
    s.headers.update({"X-AppKey": "ops.ehr-api.auth", "X-UserType": "2"})
    if not token:
        token = (s.get(BASE + "/api/auth/v1/csrf/token", timeout=15).json() or {}).get("data") or ""
    print(f"token={token}")
    url = BASE + "/api/srs/position/positionList"
    body = {"pageNum": 1, "pageSize": 3}
    header_names = ["X-CSRF", "X-Csrf", "X-CSRF-TOKEN", "X-Csrf-Token", "csrf", "csrfToken", "X-CSRFToken",
                    "csrftoken", "Aj-Csrf-Token", "aj-csrf-token"]
    for name in header_names:
        for method in ("post", "get"):
            try:
                if method == "post":
                    got = s.post(url, json=body, headers={name: token}, timeout=15)
                else:
                    got = s.get(url, params=body, headers={name: token}, timeout=15)
                print(f"[{got.status_code}] header {name} {method.upper()} -> {got.text[:180]}")
            except Exception as exc:  # noqa: BLE001
                print(f"[ERR] {name} {method} -> {exc}")
    for cname in ("csrf", "csrfToken", "ajSessionId", "CSRF-TOKEN"):
        try:
            got = s.post(url, json=body, cookies={cname: token}, timeout=15)
            print(f"[{got.status_code}] cookie {cname} -> {got.text[:180]}")
        except Exception as exc:  # noqa: BLE001
            print(f"[ERR] cookie {cname} -> {exc}")


def probe_regex(pattern: str, span: int = 160, limit: int = 40) -> None:
    """按正则打印 bundle 命中上下文（找未硬编码的请求头名）。"""
    seen = 0
    for url, js in _js_files().items():
        name = url.split("/")[-1]
        for m in re.finditer(pattern, js):
            seen += 1
            if seen > limit:
                return
            s = max(0, m.start() - span)
            print(f"{name} @{m.start()}: ...{js[s:m.end() + span]}...")


def probe_shape(pages: int = 1) -> None:
    """确认 positionList 返回结构（字段名 / 分页 / JD 完整度）。"""
    s = requests.Session()
    s.headers.update(HEADERS)
    s.headers.update({"X-AppKey": "ops.ehr-api.auth", "X-UserType": "2"})
    token = (s.get(BASE + "/api/auth/v1/csrf/token", timeout=15).json() or {}).get("data") or ""
    s.headers["X-CSRF"] = token
    for path, tag in (("/api/srs/position/positionList", "社招"),
                      ("/api/campus/position/positionList", "校招")):
        body = {"pageNum": 1, "pageSize": 100}
        got = s.post(BASE + path, json=body, timeout=20)
        payload = (got.json() or {}).get("data") or {}
        print(f"\n===== {tag} {path} -> code={got.json().get('code')} keys={list(payload)}")
        lst = payload.get("list") or []
        print(f"list={len(lst)} 其他分页字段="
              f"{ {k: v for k, v in payload.items() if k != 'list'} }")
        if lst:
            item = lst[0]
            print(f"item keys={list(item)}")
            for k, v in item.items():
                text = str(v).replace("\n", "\\n")
                print(f"  {k} = {text[:110]}")
            desc = [x for x in lst if x.get("positionDescription")]
            print(f"有 JD 的条数={len(desc)}/ {len(lst)}，JD 长度 min={min(len(x['positionDescription']) for x in desc)} "
                  f"max={max(len(x['positionDescription']) for x in desc)}") if desc else print("无 JD 字段")


if __name__ == "__main__":
    if "--shape" in sys.argv:
        probe_shape()
    elif "--regex" in sys.argv:
        probe_csrf(sys.argv[sys.argv.index("--csrf") + 1] if len(sys.argv) > sys.argv.index("--csrf") + 1 else None)
    elif "--keys" in sys.argv:
        probe_keys(*[a for a in sys.argv[sys.argv.index("--keys") + 1:] if not a.startswith("--")])
    elif "--call" in sys.argv:
        probe_calls()
    elif "--try" in sys.argv:
        probe_try()
    elif "--js" in sys.argv:
        probe_js()
    elif "--sess" in sys.argv:
        probe_session()
    else:
        for path in CANDIDATES:
            try:
                r = requests.get(BASE + path, headers=HEADERS, timeout=15,
                                 params={"pageNum": 1, "pageSize": 10})
                print(f"[{r.status_code}] GET {path} -> {r.text[:200]}")
            except Exception as exc:  # noqa: BLE001
                print(f"[ERR] {path} -> {exc}")

