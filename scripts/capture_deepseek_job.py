"""捕获 Moka 岗位详情接口的请求体 + 响应结构。"""
import json

from playwright.sync_api import sync_playwright

captured = []
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()

    def on_response(resp):
        if "website/job" in resp.url and resp.request.method == "POST":
            try:
                captured.append((resp.request.post_data, resp.json()))
            except Exception:  # noqa: BLE001
                pass

    page.on("response", on_response)
    page.goto("https://app.mokahr.com/social-recruitment/high-flyer/140576#/job/2eb2e75d-29f3-47b5-bb10-39f12547d39",
              wait_until="domcontentloaded", timeout=40000)
    page.wait_for_timeout(6000)
    browser.close()

print("捕获数:", len(captured))
for i, (body, resp) in enumerate(captured):
    print(f"=== 第{i+1}个 请求体 ===")
    print(body)
    print("=== 响应 ===")
    print(json.dumps(resp, ensure_ascii=False)[:1000])
    print()
