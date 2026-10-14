"""捕获小米校招接口响应结构。"""
import json

from playwright.sync_api import sync_playwright

captured = []
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()

    def on_response(resp):
        if "/api/v1/search/job/posts" in resp.url:
            try:
                captured.append(resp.json())
            except Exception:  # noqa: BLE001
                pass

    page.on("response", on_response)
    page.goto("https://xiaomi.jobs.f.mioffice.cn/campus/",
              wait_until="domcontentloaded", timeout=40000)
    page.wait_for_timeout(6000)
    for _ in range(10):
        page.evaluate("""() => {
          const el = document.querySelector('.isInVisualWebsiteUIFeat')
                  || document.querySelector('main') || document.scrollingElement;
          if (el) el.scrollTop = el.scrollHeight;
        }""")
        page.wait_for_timeout(1200)
    browser.close()

print("捕获响应数:", len(captured))
if captured:
    d = captured[0]
    data = d.get("data") or {}
    posts = data.get("job_post_list") or []
    print("data keys:", list(data.keys()))
    print("本批岗位数:", len(posts))
    if posts:
        print("第一条 keys:", list(posts[0].keys()))
        print(json.dumps(posts[0], ensure_ascii=False)[:1200])
