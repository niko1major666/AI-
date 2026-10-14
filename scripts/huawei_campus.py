"""深入探查华为校招站：最终 URL + 职位相关链接 + 所有请求。"""
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()
    requests = []
    page.on("request", lambda req: requests.append((req.method, req.url)))

    page.goto("https://career.huawei.com/reccampportal/campus4_index.html",
              wait_until="domcontentloaded", timeout=40000)
    page.wait_for_timeout(6000)

    print("=== 最终 URL ===")
    print(" ", page.url)

    print("=== 职位/招聘相关链接 ===")
    links = page.evaluate("""() => {
      return Array.from(document.querySelectorAll('a')).map(a => ({
        text: (a.textContent||'').trim().slice(0,20), href: a.href
      })).filter(x => /职位|招聘|岗位|job|position|campus/i.test(x.text) || /job|position|campus/i.test(x.href));
    }""")
    for l in links[:30]:
        print(f"  '{l['text']}' -> {l['href'][:150]}")

    print("=== 所有相关请求 ===")
    for method, u in requests:
        if any(k in u.lower() for k in ["job", "position", "search", "campus", "query", "get"]):
            print(f"  {method} {u[:250]}")

    browser.close()
