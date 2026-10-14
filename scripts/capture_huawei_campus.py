"""捕获华为校招接口真实响应，确认岗位数量。"""
import json

from playwright.sync_api import sync_playwright

captured = []
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()

    def on_response(resp):
        if "getJob/newHr" in resp.url and "jobTypes=7" in resp.url:
            try:
                captured.append(resp.json())
            except Exception:  # noqa: BLE001
                pass

    page.on("response", on_response)
    page.goto("https://career.huawei.com/reccampportal/portal5/campus-recruitment.html",
              wait_until="domcontentloaded", timeout=40000)
    page.wait_for_timeout(8000)
    browser.close()

print("捕获响应数:", len(captured))
for d in captured:
    p = d.get("pageVO") or {}
    r = d.get("result") or []
    print(f"totalRows={p.get('totalRows')} totalPages={p.get('totalPages')} 本页={len(r)}")
    for x in r[:8]:
        print("  -", x.get("nameCn"), "|", x.get("jobAddress"))
    # 打印第一条完整字段
    if r:
        print("第一条 keys:", list(r[0].keys()))
