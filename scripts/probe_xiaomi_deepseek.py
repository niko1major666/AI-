"""探测小米 / DeepSeek 招聘站点可达性与接口。"""
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
}


def check(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        ct = r.headers.get("content-type", "")
        print(f"[{r.status_code}] {url} -> {ct.split(';')[0]} ({len(r.text)}B) 最终:{r.url[:80]}")
        return r
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] {url} -> {type(e).__name__}: {e}")
        return None


for u in [
    "https://xiaomi.jobs.com/",
    "https://hr.xiaomi.com/",
    "https://zhaopin.xiaomi.com/",
    "https://www.deepseek.com/",
    "https://careers.deepseek.com/",
    "https://job.deepseek.com/",
]:
    check(u)
