"""华为：找搜索按钮并点击，拦截真实搜索请求。"""
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()
    requests = []
    page.on("request", lambda req: requests.append((req.method, req.url)))

    page.goto("https://career.huawei.com/reccampportal/portal5/social-recruitment.html",
              wait_until="domcontentloaded", timeout=40000)
    page.wait_for_timeout(5000)

    btns = page.evaluate("""() => {
      return Array.from(document.querySelectorAll('button, a, span, div, i'))
        .map(el => ({tag: el.tagName, text: (el.textContent||'').trim().slice(0,20),
                     cls: (el.className||'').toString().slice(0,50)}))
        .filter(b => /搜索|search|Search|放大|🔍/.test(b.text) || /search/i.test(b.cls));
    }""")
    print("=== 搜索相关按钮 ===")
    for b in btns:
        print(f"  <{b['tag']}> '{b['text']}' class='{b['cls']}'")

    # 填关键词 + 点搜索按钮
    try:
        page.fill("input[type=text]", "算法")
        # 尝试点击常见搜索按钮选择器
        for sel in ["button:has-text('搜索')", "a:has-text('搜索')", ".search-btn",
                    "button[type=submit]", "i.fa-search", ".icon-search"]:
            loc = page.locator(sel).first
            if loc.count() > 0:
                loc.click()
                page.wait_for_timeout(5000)
                break
        print("=== 点击后的请求 ===")
        for method, u in requests:
            if "getJob" in u:
                print(f"  {method} {u[:250]}")
    except Exception as e:  # noqa: BLE001
        print("交互失败:", type(e).__name__, e)

    browser.close()
