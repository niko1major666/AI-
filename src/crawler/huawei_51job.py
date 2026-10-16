"""华为 AI 岗位爬虫（51job 第三方平台，Playwright 拦截 search-pc 接口）。

说明：华为门户岗位极少（社招 2 / 校招 0），改用 51job 搜索「华为」公司名
精准匹配华为公司职位，拦截 search-pc 接口（无需登录）拿到职位列表。
完整 JD 详情需登录，故用 jobName + jobTags（技能标签）拼成技能文本。

实测结论：9 城市仅 3 条 AI 相关岗且无完整 JD（jd_text 过短会被清洗过滤），
故产出未并入主数据，仅作为「华为第三方补充」的技术尝试留存。

城市代码：北京010000 上海020000 深圳040000 杭州080000 南京070000
         成都090000 武汉180000 西安200000 东莞190000
"""
from __future__ import annotations

import re

import pandas as pd
from playwright.sync_api import sync_playwright

AI_KEYWORDS = ["算法", "AI", "大模型", "机器学习", "深度学习", "计算机视觉",
               "自然语言处理", "NLP", "CV", "强化学习", "昇腾", "自动驾驶",
               "智能驾驶", "语音", "图像", "推荐", "数据挖掘", "多模态"]

CITIES = ["040000", "010000", "020000", "080000", "070000", "090000", "180000", "200000", "190000"]


def _capture(city: str, scroll_times: int = 18) -> list[dict]:
    captured = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()

        def on_response(resp):
            if "search-pc" in resp.url:
                try:
                    captured.append(resp.json())
                except Exception:  # noqa: BLE001
                    pass

        page.on("response", on_response)
        url = (f"https://we.51job.com/pc/search?jobArea={city}&keyword="
               + "%E5%8D%8E%E4%B8%BA&searchType=2")
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(4000)
        for _ in range(scroll_times):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2200)
        browser.close()
    return captured


def _is_ai(name: str, tags: list[str]) -> bool:
    text = " ".join([name] + list(tags))
    for k in AI_KEYWORDS:
        if k.isascii():
            # 英文关键词用词边界，避免 "AI" 误匹配 "AIDC"
            if re.search(r"(?<![a-zA-Z0-9])" + re.escape(k) + r"(?![a-zA-Z0-9])", text, re.I):
                return True
        else:
            if k in text:
                return True
    return False


def crawl(cities=CITIES) -> list[dict]:
    rows = []
    seen = set()
    for city in cities:
        captured = _capture(city)
        for d in captured:
            items = (d.get("resultbody") or {}).get("job", {}).get("items", [])
            for it in items:
                jid = it.get("jobId")
                if not jid or jid in seen:
                    continue
                name = it.get("jobName") or ""
                tags = it.get("jobTags") or []
                if not _is_ai(name, tags):
                    continue
                seen.add(jid)
                rows.append({
                    "job_id": f"hw51_{jid}",
                    "company": "华为",
                    "title": name,
                    "location": it.get("jobAreaString") or "",
                    "salary": it.get("provideSalaryString") or "",
                    "experience": it.get("workYearString") or "",
                    "education": it.get("degreeString") or "",
                    "jd_text": " ".join([name] + list(tags)),
                    "department": it.get("industryType1Str") or "",
                    "publish_time": (it.get("issueDateString") or "")[:10],
                })
        print(f"city={city} 累计 {len(rows)} 条")
    return rows


def main():
    rows = crawl()
    df = pd.DataFrame(rows).drop_duplicates(subset="job_id")
    out = "data/raw/huawei_51job_jobs.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"华为 AI 岗位共 {len(df)} 条 → {out}")


if __name__ == "__main__":
    main()
