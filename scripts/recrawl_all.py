"""顺序重爬全部数据源（补 department/publish_time 字段）。"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CRAWLERS = ["tencent", "xiaomi", "huawei", "deepseek", "xiaomi_campus", "bytedance",
            "kimi", "minimax", "kuaishou", "xiaohongshu", "bilibili", "didi"]


def main():
    for c in CRAWLERS:
        print(f"\n===== 爬取 {c} =====", flush=True)
        r = subprocess.run([sys.executable, "-m", f"src.crawler.{c}"], cwd=str(ROOT))
        print(f"===== {c} 退出码 {r.returncode} =====", flush=True)
    print("全部完成")


if __name__ == "__main__":
    main()
