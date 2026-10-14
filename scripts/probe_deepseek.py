"""探测 DeepSeek 招聘入口与接口。"""
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()
    requests = []
    page.on("request", lambda req: requests.append((req.method, req.url)))

    page.goto("https://www.deepseek.com/", wait_until="domcontentloaded", timeout=40000)
    page.wait_for_timeout(5000)

    links = page.evaluate("""() => {
      return Array.from(document.querySelectorAll('a')).map(a => ({
        text: (a.textContent||'').trim().slice(0,25), href: a.href
      })).filter(x => /join|career|hiring|recruit|job|招聘|加入|岗位|职位/i.test(x.text + ' ' + x.href));
    }""")
    print("=== 招聘/加入相关链接 ===")
    for l in links[:25]:
        print(f"  '{l['text']}' -> {l['href'][:130]}")

    print("=== API/岗位相关请求 ===")
    for m, u in requests:
        if any(k in u.lower() for k in ["api", "job", "career", "position", "recruit", "join"]):
            print(f"  {m} {u[:160]}")

    browser.close()
