"""侦察 talent.didiglobal.com 的公开接口（只读，临时脚本）。

站点是 Vue SPA：首页 HTML 只有 1.7KB 壳，入口 ESM（`/home/recruit-portal-home.*.js`）
里**不含**任何 `/api` 字符串——接口路径要等运行时才发出来。定位方式是 Playwright
打开 `/social/`，抓 XHR（`page.on("request")`），得到：

    GET /recruit-portal-service/api/job/front/list?page=1&size=10

用法：
  python scripts/probe_didi.py           # 打列表接口，打印 total / 字段 / 职位类型分布
  python scripts/probe_didi.py --size    # 试探分页 size 上限（>100 被网关拦截：code=10039）
  python scripts/probe_didi.py --net     # 用 Playwright 重抓一遍 SPA 发出的请求
  python scripts/probe_didi.py --campus  # 看校招站（Moka ATS，响应体加密）

校招不在本域名：`talent.didiglobal.com/campus/` 只是跳转页，真正的校招投递在
`campus.didiglobal.com`（Moka），岗位列表接口 `/api/outer/ats-apply/website/jobs`
返回 AES 密文（`{"data": "<base64>"}`），没有公开明文接口。
"""
from __future__ import annotations

import base64
import collections
import sys

import requests

BASE = "https://talent.didiglobal.com"
LIST_PATH = "/recruit-portal-service/api/job/front/list"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": BASE + "/social",
    "Accept": "application/json, text/plain, */*",
}
CAMPUS_ORG = "didiglobal"
CAMPUS_SITE = 96064


def probe_list(pages: int = 2) -> None:
    """打印总数、字段名、职位类型分布与 JD 正文长度。"""
    s = requests.Session()
    s.headers.update(HEADERS)
    items: list[dict] = []
    total = 0
    for page in range(1, pages + 1):
        got = s.get(BASE + LIST_PATH, params={"page": page, "size": 100}, timeout=30)
        data = (got.json() or {}).get("data") or {}
        total = int(data.get("total") or 0)
        batch = data.get("items") or []
        items.extend(batch)
        print(f"[{got.status_code}] page {page} -> +{len(batch)}，total={total}")
        if not batch:
            break
    if not items:
        return
    print(f"item keys = {list(items[0])}")
    for k, v in items[0].items():
        text = str(v).replace("\n", "\\n")
        print(f"  {k} = {text[:100]}")
    counts = collections.Counter(i.get("jobTypeName") for i in items)
    print("职位类型分布：" + "、".join(f"{k}×{v}" for k, v in counts.most_common()))
    lens = [len(i.get("jobDuty") or "") + len(i.get("jobQualification") or "")
            for i in items]
    print(f"JD 正文长度 min={min(lens)} max={max(lens)} avg={sum(lens) // len(lens)}")


def probe_size() -> None:
    """size 上限：100 正常，200 被网关拦截（code=10039 / data=null）。"""
    s = requests.Session()
    s.headers.update(HEADERS)
    for size in (10, 50, 100, 200):
        got = s.get(BASE + LIST_PATH, params={"page": 1, "size": size}, timeout=30)
        data = (got.json() or {}).get("data") or {}
        print(f"size={size} -> status={got.status_code} "
              f"items={len(data.get('items') or [])} total={data.get('total')}")


def probe_net() -> None:
    """用 Playwright 打开社招页，打印 SPA 实际发出的接口请求（定位新接口时用）。"""
    from playwright.sync_api import sync_playwright

    hits: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_context(viewport={"width": 1400, "height": 1000}).new_page()
        page.on("request", lambda r: hits.append(f"{r.method} {r.url}")
                if "didistatic" not in r.url and "omg" not in r.url else None)
        page.goto(BASE + "/social/", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(4000)
        browser.close()
    for line in hits:
        print(line)


def probe_campus() -> None:
    """校招站（Moka）：列表接口在，但响应是 AES 密文。"""
    url = "https://campus.didiglobal.com/api/outer/ats-apply/website/jobs"
    body = {"orgId": CAMPUS_ORG, "siteId": CAMPUS_SITE, "locale": "zh-CN",
            "limit": 10, "offset": 0}
    got = requests.post(url, json=body, timeout=20, headers={
        "User-Agent": HEADERS["User-Agent"],
        "Referer": f"https://campus.didiglobal.com/campus_apply/{CAMPUS_ORG}/{CAMPUS_SITE}",
        "Content-Type": "application/json"})
    print(f"[{got.status_code}] {url}")
    data = (got.json() or {}).get("data")
    if isinstance(data, str):
        try:
            raw = base64.b64decode(data + "==")
            print(f"  返回 base64 密文：{len(data)} 字符 → {len(raw)} 字节，头部 {raw[:16]!r}")
        except Exception:  # noqa: BLE001
            print(f"  返回 data（非 JSON 对象）：{data[:60]}")
        print("  → Moka 前端用 crypto-js 解密（AES 密钥在各站点 bundle 里），暂无公开明文接口")
    else:
        print(f"  data 类型 {type(data)}：{str(data)[:120]}")


if __name__ == "__main__":
    if "--size" in sys.argv:
        probe_size()
    elif "--net" in sys.argv:
        probe_net()
    elif "--campus" in sys.argv:
        probe_campus()
    else:
        probe_list()
