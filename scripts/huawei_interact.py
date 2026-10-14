"""用 Playwright 与华为招聘页交互，找到真实搜索接口。"""
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()
    requests = []
    page.on("request", lambda req: requests.append((req.method, req.url)))

    page.goto("https://career.huawei.com/reccampportal/portal5/social-recruitment.html",
              wait_until="domcontentloaded", timeout=40000)
    page.wait_for_timeout(5000)

    inputs = page.evaluate("""() => {
      return Array.from(document.querySelectorAll('input')).map(i => ({
        type: i.type, ph: i.placeholder, id: i.id, cls: (i.className||'').toString().slice(0,60)
      }));
    }""")
    print("=== input 元素 ===")
    for i in inputs:
        print(f"  type={i['type']} placeholder='{i['ph']}' id='{i['id']}' class='{i['cls']}'")

    # 尝试填充第一个文本输入框并回车
    try:
        box = page.locator("input[type=text]").first
        if box:
            box.fill("算法")
            box.press("Enter")
            page.wait_for_timeout(5000)
            print("=== 输入算法后新增的请求 ===")
            for method, u in requests:
                if "getJob" in u or "search" in u or "query" in u or "job" in u.lower():
                    print(f"  {method} {u[:200]}")
    except Exception as e:  # noqa: BLE001
        print("交互失败:", e)

    browser.close()
