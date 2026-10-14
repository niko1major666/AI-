"""用 Playwright 打开招聘站，滚动触发懒加载，捕获岗位相关请求/响应。"""
import asyncio
import sys

from playwright.async_api import async_playwright


async def main(url):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        requests = []
        responses = []

        page.on("request", lambda req: requests.append((req.method, req.url)))
        page.on("response", lambda resp: responses.append(resp.url))

        await page.goto(url, timeout=40000, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        for _ in range(6):
            await page.mouse.wheel(0, 2500)
            await page.wait_for_timeout(1200)

        keys = ("job", "post", "position", "search", "list")
        print("=== 岗位相关请求 ===")
        for method, u in requests:
            if any(k in u.lower() for k in keys):
                print(f"  {method} {u}")

        print("=== 岗位相关 JSON 响应 ===")
        for u in responses:
            if any(k in u.lower() for k in keys):
                print(f"  {u}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
