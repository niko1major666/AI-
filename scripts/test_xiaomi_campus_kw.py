"""测小米校招 URL keyword 参数 + 岗位总数。"""
from playwright.sync_api import sync_playwright

for kw in ["", "AI", "算法", "自动驾驶"]:
    captured = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()

        def on_response(resp):
            if "search/job/posts" in resp.url:
                try:
                    captured.append(resp.json())
                except Exception:  # noqa: BLE001
                    pass

        page.on("response", on_response)
        page.goto(f"https://xiaomi.jobs.f.mioffice.cn/campus/?keyword={kw}",
                  wait_until="domcontentloaded", timeout=40000)
        page.wait_for_timeout(5000)
        browser.close()
    if captured:
        data = captured[0].get("data") or {}
        print(f"keyword='{kw}' -> count={data.get('count')} 本批={len(data.get('job_post_list') or [])}")
    else:
        print(f"keyword='{kw}' -> 无响应")
