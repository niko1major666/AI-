"""探测字节跳动 / 华为招聘接口。"""
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}


def try_req(method, url, **kw):
    try:
        r = requests.request(method, url, headers=HEADERS, timeout=15, **kw)
        print(f"[{method}] {url}\n    status={r.status_code} len={len(r.text)}\n    {r.text[:180]}\n")
    except Exception as e:  # noqa: BLE001
        print(f"[{method}] {url}\n    FAIL: {type(e).__name__}: {e}\n")


print("=== 字节跳动 ===")
try_req("GET", "https://jobs.bytedance.com/api/v1/search/job/posts",
        params={"keyword": "AI", "limit": 5, "offset": 0})
try_req("POST", "https://jobs.bytedance.com/api/v1/search/job/posts",
        json={"keyword": "AI", "limit": 5, "offset": 0, "job_category_id_list": []})
try_req("GET", "https://jobs.bytedance.com/api/v1/search/job/posts",
        params={"keyword": "AI", "limit": 5},
        headers={**HEADERS, "Referer": "https://jobs.bytedance.com/experienced/position"})

print("=== 华为 ===")
try_req("GET", "https://career.huawei.com/reccampportal/portal5/social-recruitment.html")
try_req("GET", "https://career.huawei.com/reccampportal/services/portal/portalportal/queryJobList",
        params={"jobType": "0", "keyWord": "AI", "pageNo": 1, "pageSize": 5})
