"""找小米招聘子页面链接，并尝试常见岗位接口。"""
import requests

from playwright.sync_api import sync_playwright

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://hr.xiaomi.com/", wait_until="domcontentloaded", timeout=40000)
    page.wait_for_timeout(6000)

    links = page.evaluate("""() => {
      return Array.from(document.querySelectorAll('a')).map(a => ({
        text: (a.textContent||'').trim().slice(0,20), href: a.href
      })).filter(x => /招聘|职位|岗位|社招|校招|social|campus|position|job/i.test(x.text) || /position|job|recruit|social|campus/i.test(x.href));
    }""")
    print("=== 招聘相关链接 ===")
    for l in links[:25]:
        print(f"  '{l['text']}' -> {l['href'][:130]}")
    browser.close()

print()
print("=== 尝试常见岗位接口 ===")
base = "https://hr.xiaomi.com/website/cli/api/hrportal/domestic"
for path in ["position/list", "job/list", "recruit/list", "post/list", "position/page"]:
    try:
        r = requests.post(f"{base}/{path}", headers=H, json={}, timeout=10)
        print(f"  POST /{path} -> {r.status_code} {r.text[:120]}")
    except Exception as e:  # noqa: BLE001
        print(f"  /{path} -> FAIL {type(e).__name__}")
