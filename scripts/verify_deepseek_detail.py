"""验证：Moka 详情页 JS 解密后，岗位描述是否在 DOM 明文里。"""
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://app.mokahr.com/social-recruitment/high-flyer/140576#/job/2eb2e75d-29f3-47b5-bb10-39f12547d39",
              wait_until="domcontentloaded", timeout=40000)
    page.wait_for_timeout(8000)  # 等 JS 解密 + 渲染
    text = page.inner_text("body")
    print(text[:2500])
    browser.close()
