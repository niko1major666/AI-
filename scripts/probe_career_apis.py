"""探测各家大厂招聘官网的 JSON 接口是否可达（用于确定爬虫方案）。"""
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

ENDPOINTS = [
    ("字节跳动", "https://jobs.bytedance.com/api/v1/search/job/posts",
     {"keyword": "AI", "limit": 3, "offset": 0}),
    ("字节跳动-算法", "https://jobs.bytedance.com/api/v1/search/job/posts",
     {"keyword": "算法", "limit": 3, "offset": 0}),
    ("华为", "https://career.huawei.com/reccampportal/services/portal/portalportal/queryJobList",
     {"jobType": "0", "keyWord": "AI", "pageNo": 1, "pageSize": 5}),
    ("腾讯", "https://careers.tencent.com/tencentcareer/api/post/Query",
     {"keyword": "AI", "pageIndex": 1, "pageSize": 5}),
    ("百度", "https://talent.baidu.com/httservice/getPostListNew",
     {"recruitType": "SOCIAL", "keyWord": "AI", "pageNum": 1, "pageSize": 5}),
]


def probe():
    for name, url, params in ENDPOINTS:
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=15)
            body = r.text[:200].replace("\n", " ")
            print(f"[{name}] status={r.status_code} len={len(r.text)}")
            print(f"    {body}")
        except Exception as e:  # noqa: BLE001
            print(f"[{name}] FAIL: {type(e).__name__}: {e}")
        print()


if __name__ == "__main__":
    probe()
