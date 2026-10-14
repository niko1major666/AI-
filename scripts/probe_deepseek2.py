"""深入探测 DeepSeek talent 站：全部请求 + 链接。"""
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()
    requests = []
    page.on("request", lambda req: requests.append((req.method, req.url)))

    page.goto("https://talent.deepseek.com/", wait_until="domcontentloaded", timeout=40000)
    page.wait_for_timeout(6000)

    print("=== 全部请求 ===")
    for m, u in requests:
        print(f"  {m} {u[:150]}")

    print("=== 链接/按钮 ===")
    links = page.evaluate("""() => {
      return Array.from(document.querySelectorAll('a, button')).map(a => ({
        tag: a.tagName, text: (a.textContent||'').trim().slice(0,25), href: a.href||''
      })).filter(x => x.text || x.href);
    }""")
    for l in links[:30]:
        print(f"  <{l['tag']}> '{l['text']}' {l['href'][:100]}")

    browser.close()
