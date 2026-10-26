"""侦察 job.meituan.com 的公开接口（只读，临时脚本）。

移动端 SPA（`/m/position`，与 `zhaopin.meituan.com` 同一套后端）的列表接口是
POST JSON，**无 token / 签名 / cookie**：

    POST /api/official/mobile/job/getJobList
    {"page": {"pageSize": 200, "pageNo": 1}, "jobShareType": "1",
     "u_query_id": "<32 位 hex>", "r_query_id": "<毫秒时间戳 + 8 位随机数字>"}
    -> {"status": 1, "data": {"list": [...],
        "page": {"pageNo": 1, "pageSize": 200, "totalPage": 17, "totalCount": 3231}}}

定位方式与滴滴相同：页面是 Owl + ESM 的 SPA，入口 bundle（`bundle-main-*.js`，7KB）
里没有接口字符串，只有运行时才发得出来；这里用 Playwright 抓 `/m/position` 的 XHR。

四个实测结论：

1. **分页参数必须嵌在 `page` 里**。PC 那版 `/api/official/job/getJobList` 收顶层
   `pageNo`/`pageSize` 且把 `pageSize` 锁死 20（传 50/100/200 都返回 20 条）；
   移动端这版只认嵌套结构，`pageSize` 实测上限 1000（传 2000 被截到 1000），
   爬虫固定用 200（17 页抓完 3231 条）。
2. `u_query_id` / `r_query_id` 是「本次查询」的 token，**整轮翻页必须复用同一个**：
   每页换新 token 会被当成新搜索，永远返回第 1 页（`--token` 可复现：17 页只有 200 条
   唯一岗位，而 `totalCount` 一直是 3231）。
3. `jobShareType=1` 是社招（3231 条，JD 全文齐全）；`=2`（2326 条）不需要 token，
   但 `jobDuty` / `jobRequirement` **全为空**，只有标题和城市，不能用于技能抽取。
4. 校招 / 实习不在移动端这套参数里，走 PC 版的 `jobType` 过滤：
   `[{"code":"1"}]` 校招 196 条、`[{"code":"2"}]` 实习 371 条、两者 567 条（JD 同样齐全）。
   本仓库只接社招，校招/实习留作后续数据源。

用法：
  python scripts/probe_meituan.py            # 列表接口：total / 字段 / 类别分布
  python scripts/probe_meituan.py --size     # 两版接口的 pageSize 上限对比
  python scripts/probe_meituan.py --token    # 复现「每页换 token 退回第 1 页」
  python scripts/probe_meituan.py --share    # 三种 jobShareType 的条数与正文填充率
  python scripts/probe_meituan.py --campus   # PC 版校招 / 实习的 jobType 过滤
  python scripts/probe_meituan.py --net      # 用 Playwright 重抓一遍 SPA 发出的请求
"""
from __future__ import annotations

import argparse
import collections
import sys
import uuid

import requests

BASE = "https://job.meituan.com"
BASE_PC = "https://zhaopin.meituan.com"
MOBILE_PATH = "/api/official/mobile/job/getJobList"
PC_PATH = "/api/official/job/getJobList"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                  "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                  "Mobile/15E148 Safari/604.1",
    "Referer": BASE + "/m/position",
    "Origin": BASE,
    "Content-Type": "application/json",
}


def new_token() -> dict:
    return {"u_query_id": uuid.uuid4().hex,
            "r_query_id": "179301369533192399141"}


def post_mobile(body: dict) -> dict:
    payload = requests.post(BASE + MOBILE_PATH, headers=HEADERS, json=body, timeout=60).json()
    if payload.get("status") != 1:
        raise RuntimeError(f"接口异常：{payload.get('status')} {payload.get('message')}")
    return payload.get("data") or {}


def page_body(page: int, size: int, share: str = "1", token: dict | None = None) -> dict:
    return {"page": {"pageSize": size, "pageNo": page}, "jobShareType": share,
            **(token or new_token())}


def probe_list(pages: int = 2) -> None:
    token = new_token()
    rows, total = [], 0
    for page in range(1, pages + 1):
        data = post_mobile(page_body(page, 100, token=token))
        rows.extend(data.get("list") or [])
        total = (data.get("page") or {}).get("totalCount") or 0
    print(f"total={total}，本批 {len(rows)} 条")
    if not rows:
        return
    print("字段:", list(rows[0]))
    print("类别:", collections.Counter(r.get("jobFamily") for r in rows).most_common())
    print("技术类细分:", collections.Counter(r.get("jobFamilyGroup") for r in rows
                                              if r.get("jobFamily") == "技术类").most_common())
    lens = [len(r.get("jobDuty") or "") + len(r.get("jobRequirement") or "") for r in rows]
    print(f"正文长度 min={min(lens)} max={max(lens)} 空正文={sum(1 for x in lens if x == 0)}")
    print("样例:", [(r["name"], r.get("jobFamily"), r["jobDuty"][:20]) for r in rows[:3]])


def probe_size() -> None:
    print("== PC 版：pageSize 被服务端锁死 20 ==")
    pc_headers = dict(HEADERS, Referer=BASE_PC + "/web/social")
    for size in (20, 50, 100, 200):
        d = requests.post(BASE_PC + PC_PATH, headers=pc_headers,
                          json={"pageNo": 1, "pageSize": size}, timeout=40).json()
        data = d.get("data") or {}
        print(f"  pageSize={size} -> 返回 {len(data.get('list') or [])} 条，"
              f"page={data.get('page')}")
    print("== 移动版：嵌套 page，实测 pageSize 上限 1000 ==")
    for size in (10, 50, 100, 200, 500, 1000, 2000):
        data = post_mobile(page_body(1, size))
        pg = data.get("page") or {}
        print(f"  pageSize={size} -> 返回 {len(data.get('list') or [])} 条，"
              f"totalPage={pg.get('totalPage')}")


def probe_token() -> None:
    """同一 token 翻页会换批；换新 token 再翻第 2 页会退回第 1 页。"""
    token = new_token()
    p1 = post_mobile(page_body(1, 5, token=token)).get("list") or []
    p2 = post_mobile(page_body(2, 5, token=token)).get("list") or []
    other = new_token()
    p2_other = post_mobile(page_body(2, 5, token=other)).get("list") or []
    ids = lambda rows: [r["jobUnionId"] for r in rows]  # noqa: E731
    print("同 token 第 1 页:", ids(p1))
    print("同 token 第 2 页:", ids(p2))
    print("换 token 第 2 页:", ids(p2_other))
    print("→ 同 token 两页是否重叠:", bool(set(ids(p1)) & set(ids(p2))))
    print("→ 换 token 后是否与第 1 页重叠:", bool(set(ids(p1)) & set(ids(p2_other))))


def probe_share() -> None:
    for share in ("1", "2", "3"):
        data = post_mobile(page_body(1, 100, share=share))
        rows = data.get("list") or []
        if not rows:
            print(f"jobShareType={share}: 0 条（缺 u_query_id/r_query_id 时为 0）")
            continue
        empty = sum(1 for r in rows if not (r.get("jobDuty") or "").strip())
        print(f"jobShareType={share}: total={(data.get('page') or {}).get('totalCount')} "
              f"n={len(rows)} 空正文={empty}")


def probe_campus() -> None:
    """校招 / 实习走 PC 版 jobType 过滤（1=校招，2=实习）。"""
    token = new_token()
    pc_headers = dict(HEADERS, Referer=BASE_PC + "/web/campus")
    for label, types in (("校招 1", [{"code": "1", "subCode": []}]),
                         ("实习 2", [{"code": "2", "subCode": []}]),
                         ("校招+实习", [{"code": "1", "subCode": []},
                                        {"code": "2", "subCode": []}])):
        body = {"page": {"pageNo": 1, "pageSize": 100}, "jobShareType": "1", "keywords": "",
                "cityList": [], "department": [], "jfJgList": [], "jobType": types,
                "typeCode": [], "specialCode": [], **token}
        d = requests.post(BASE_PC + PC_PATH, headers=pc_headers, json=body, timeout=40).json()
        data = d.get("data") or {}
        rows = data.get("list") or []
        tech = sum(1 for r in rows if r.get("jobFamily") == "技术类")
        print(f"{label}: total={(data.get('page') or {}).get('totalCount')} "
              f"本批 {len(rows)} 条（技术类 {tech}）")


def probe_net() -> None:
    """用 Playwright 重抓一遍 /m/position 发出的 XHR，确认接口与请求体没变。"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        page = ctx.new_page()
        seen = []
        page.on("request", lambda r: seen.append((r.method, r.url, r.post_data))
                if "getJobList" in r.url else None)
        page.goto(BASE + "/m/position", wait_until="networkidle", timeout=90000)
        page.wait_for_timeout(4000)
        for method, url, body in seen:
            print(f"{method} {url}\n  body={body}")
        browser.close()


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="侦察美团招聘接口")
    parser.add_argument("--size", action="store_true", help="pageSize 上限对比")
    parser.add_argument("--token", action="store_true", help="验证 token 必须整轮复用")
    parser.add_argument("--share", action="store_true", help="三种 jobShareType 对比")
    parser.add_argument("--campus", action="store_true", help="校招 / 实习的 jobType 过滤")
    parser.add_argument("--net", action="store_true", help="Playwright 重抓 SPA 请求")
    parser.add_argument("--pages", type=int, default=2, help="默认模式抓几页")
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    if args.size:
        probe_size()
    elif args.token:
        probe_token()
    elif args.share:
        probe_share()
    elif args.campus:
        probe_campus()
    elif args.net:
        probe_net()
    else:
        probe_list(args.pages)


if __name__ == "__main__":
    main()
