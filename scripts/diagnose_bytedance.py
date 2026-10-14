"""诊断字节岗位页：找可滚动容器 + 加载更多按钮。"""
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://jobs.bytedance.com/experienced/position?keywords=AI",
              wait_until="domcontentloaded", timeout=40000)
    page.wait_for_timeout(5000)

    scrollables = page.evaluate("""
    () => {
      const all = document.querySelectorAll('*');
      const result = [];
      all.forEach(el => {
        if (el.scrollHeight > el.clientHeight + 50 && el.clientHeight > 100) {
          result.push({tag: el.tagName, cls: (el.className||'').toString().slice(0,60),
                       sh: el.scrollHeight, ch: el.clientHeight});
        }
      });
      return result.slice(0, 20);
    }
    """)
    print("=== 可滚动元素 ===")
    for s in scrollables:
        print(f"  <{s['tag']}> class='{s['cls']}' scrollH={s['sh']} clientH={s['ch']}")

    btns = page.evaluate("""
    () => {
      const all = document.querySelectorAll('button, [role=button], div, span');
      const result = [];
      all.forEach(el => {
        const t = (el.textContent||'').trim();
        if (t && t.length < 25 && (t.includes('加载更多') || t.includes('查看更多')
            || t.toLowerCase().includes('load more') || t.includes('展开'))) {
          result.push({tag: el.tagName, text: t, cls: (el.className||'').toString().slice(0,50)});
        }
      });
      return result.slice(0, 15);
    }
    """)
    print("=== 加载更多相关按钮 ===")
    for b in btns:
        print(f"  <{b['tag']}> '{b['text']}' class='{b['cls']}'")

    browser.close()
