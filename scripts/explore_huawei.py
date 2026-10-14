"""探测华为招聘接口响应结构。"""
import json

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://career.huawei.com/reccampportal/portal5/social-recruitment.html",
}

URL = "https://career.huawei.com/reccampportal/services/portal/portalpub/getJob/newHr/page/10/1"


def main():
    params = {"curPage": 1, "pageSize": 5, "jobFamilyCode": "", "deptCode": "",
              "keywords": "AI", "searchType": 1, "orderBy": "P_COUNT_DESC", "jobType": 1}
    r = requests.get(URL, params=params, headers=HEADERS, timeout=15)
    print("status:", r.status_code)
    data = r.json()
    print(json.dumps(data, ensure_ascii=False, indent=2)[:1800])


if __name__ == "__main__":
    main()
