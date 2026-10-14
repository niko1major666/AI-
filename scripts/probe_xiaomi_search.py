"""找小米校招站搜索框。"""
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://xiaomi.jobs.f.mioffice.cn/campus/",
              wait_until="domcontentloaded", timeout=40000)
    page.wait_for_timeout(5000)
    inputs = page.evaluate("""() => {
      return Array.from(document.querySelectorAll('input')).map(i => ({
        type: i.type, ph: i.placeholder, cls: (i.className||'').toString().slice(0,60)
      }));
    }""")
    print("=== input 元素 ===")
    for i in inputs:
        print(f"  type={i['type']} placeholder='{i['ph']}' class='{i['cls']}'")
    browser.close()
