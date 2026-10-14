"""排查华为接口的关键词搜索行为。"""
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://career.huawei.com/reccampportal/portal5/social-recruitment.html",
}
URL = "https://career.huawei.com/reccampportal/services/portal/portalpub/getJob/newHr/page/10/1"


def q(keyword, search_type=1, job_type=1):
    params = {"curPage": 1, "pageSize": 5, "jobFamilyCode": "", "deptCode": "",
              "keywords": keyword, "searchType": search_type, "orderBy": "P_COUNT_DESC",
              "jobType": job_type}
    r = requests.get(URL, params=params, headers=HEADERS, timeout=15)
    d = r.json()
    total = (d.get("pageVO") or {}).get("totalRows")
    first = (d.get("result") or [{}])[0].get("nameCn", "")
    return total, first


for kw in ["工程师", "算法工程师", "软件", "AI"]:
    for st in [1, 2]:
        try:
            total, first = q(kw, st)
            print(f"kw={kw} searchType={st} -> total={total} 首条={first}")
        except Exception as e:  # noqa: BLE001
            print(f"kw={kw} searchType={st} -> ERR {e}")
