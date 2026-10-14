"""深入探测小米 hr.xiaomi.com 与 DeepSeek 招聘入口。"""
import re

import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

r = requests.get("https://hr.xiaomi.com/", headers=H, timeout=15)
print("=== hr.xiaomi.com 内容 ===")
print(r.text[:600])
print()

r2 = requests.get("https://www.deepseek.com/", headers=H, timeout=15)
print("=== deepseek.com 招聘/职位相关链接 ===")
seen = set()
for m in re.finditer(r'href=["\']([^"\']+)["\']', r2.text, re.I):
    u = m.group(1)
    if re.search(r'career|job|join|zhaopin|hiring|position|we-are|about', u, re.I):
        if u not in seen:
            seen.add(u)
            print(" -", u[:120])
if not seen:
    print("  (无明显链接，检查 script 中的 URL)")
    # 从 script/json 中找
    for m in re.finditer(r'https?://[^"\']*?(?:career|job|zhaopin|hiring)[^"\']*', r2.text, re.I):
        print("  *", m.group(0)[:120])
