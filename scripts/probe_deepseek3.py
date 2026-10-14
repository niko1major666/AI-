"""抓 DeepSeek 岗位列表 + 探测 Moka 详情接口。"""
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()

    page.goto("https://talent.deepseek.com/", wait_until="domcontentloaded", timeout=40000)
    page.wait_for_timeout(6000)

    # 抓岗位卡片：标题 + 类别 + 地点 + 链接
    jobs = page.evaluate("""() => {
      return Array.from(document.querySelectorAll('a[href*="mokahr"]')).map(a => {
        const t = (a.textContent||'').trim().replace(/\\s+/g, ' ');
        const m = a.href.match(/job\\/([0-9a-f-]+)/i);
        return {text: t, uuid: m ? m[1] : ''};
      }).filter(x => x.uuid);
    }""")
    print(f"岗位卡片数: {len(jobs)}")
    for j in jobs[:8]:
        print(f"  {j['text'][:60]}")

    # 探测 Moka 详情 API：打开一个岗位详情页，捕获请求
    if jobs:
        detail_url = f"https://app.mokahr.com/social-recruitment/high-flyer/140576#/job/{jobs[0]['uuid']}"
        requests = []
        page.on("request", lambda req: requests.append((req.method, req.url)))
        page.goto(detail_url, wait_until="domcontentloaded", timeout=40000)
        page.wait_for_timeout(5000)
        print("=== Moka 详情页请求 ===")
        for m, u in requests:
            if "mokahr" in u or "api" in u:
                print(f"  {m} {u[:180]}")
    browser.close()
