"""快速验证：滚动字节的自定义滚动容器能否触发加载更多。"""
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
    page.goto("https://jobs.bytedance.com/experienced/position?keywords=AI",
              wait_until="domcontentloaded", timeout=40000)
    page.wait_for_timeout(3000)
    for _ in range(25):
        page.evaluate("""
        () => {
          const el = document.querySelector('.isInVisualWebsiteUIFeat')
                  || document.querySelector('main')
                  || document.scrollingElement;
          if (el) el.scrollTop = el.scrollHeight;
        }
        """)
        page.wait_for_timeout(2000)
    browser.close()

total = sum(len((d.get("data") or {}).get("job_post_list") or []) for d in captured)
print("响应数:", len(captured), "去重前岗位数:", total)
for i, d in enumerate(captured):
    posts = (d.get("data") or {}).get("job_post_list") or []
    print(f"  第{i+1}批: {len(posts)} 条")
