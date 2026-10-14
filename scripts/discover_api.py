"""用 Playwright 打开招聘站，拦截并打印 JSON API 响应，用于发现真实接口。"""
import asyncio
import sys

from playwright.async_api import async_playwright


async def main(url):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        captured = []

        async def on_response(resp):
            ct = resp.headers.get("content-type") or ""
            if "json" in ct and ("api" in resp.url or "service" in resp.url):
                try:
                    captured.append((resp.url, await resp.json()))
                except Exception:  # noqa: BLE001
                    pass

        page.on("response", on_response)
        await page.goto(url, timeout=40000, wait_until="domcontentloaded")
        await page.wait_for_timeout(10000)  # 等 SPA 加载并发起 API 请求

        print(f"捕获 {len(captured)} 个 JSON 响应")
        for u, b in captured[:8]:
            print("== URL:", u)
            print(str(b)[:400])
            print()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
