"""探索腾讯招聘接口：列表字段 + JD 详情接口。"""
import json

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://careers.tencent.com/",
}

BASE = "https://careers.tencent.com/tencentcareer/api/post"


def main():
    r = requests.get(f"{BASE}/Query", params={"keyword": "AI", "pageIndex": 1, "pageSize": 3},
                     headers=HEADERS, timeout=15)
    data = r.json()
    print("Count:", data["Data"]["Count"])
    posts = data["Data"]["Posts"]
    if posts:
        print("=== 列表第一条完整字段 ===")
        print(json.dumps(posts[0], ensure_ascii=False, indent=2))

    # 详情接口
    if posts:
        pid = posts[0]["PostId"]
        for detail_name in ("ByPostId", "Detail"):
            try:
                r2 = requests.get(f"{BASE}/{detail_name}",
                                  params={"postId": pid, "language": "zh-cn"},
                                  headers=HEADERS, timeout=15)
                print(f"=== 详情接口 {detail_name} status={r2.status_code} ===")
                print(r2.text[:600])
            except Exception as e:  # noqa: BLE001
                print(f"详情 {detail_name} FAIL: {e}")


if __name__ == "__main__":
    main()
