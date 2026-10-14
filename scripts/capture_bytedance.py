"""用 Playwright 拦截字节岗位接口响应，打印返回结构（用于写爬虫）。"""
import asyncio
import json

from playwright.async_api import async_playwright


async def main():
    captured = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()

        async def on_response(resp):
            if "/api/v1/search/job/posts" in resp.url:
                try:
                    captured.append(await resp.json())
                except Exception:  # noqa: BLE001
                    pass

        page.on("response", on_response)
        await page.goto("https://jobs.bytedance.com/experienced/position?keywords=AI",
                        wait_until="domcontentloaded", timeout=40000)
        await page.wait_for_timeout(6000)
        await browser.close()

    print("捕获响应数:", len(captured))
    if not captured:
        return
    d = captured[0]
    print("顶层 keys:", list(d.keys()))
    data = d.get("data") or {}
    if isinstance(data, dict):
        print("data keys:", list(data.keys()))
        posts = data.get("job_post_list") or data.get("job_list") or []
        if posts:
            print("第一条岗位字段:")
            print(json.dumps(posts[0], ensure_ascii=False, indent=2)[:1600])
        else:
            print("data 预览:", json.dumps(data, ensure_ascii=False)[:800])


asyncio.run(main())
