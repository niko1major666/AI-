"""环境体检：Python 版本、关键包版本 vs 锁矩阵、磁盘、缓存目录。"""
import importlib
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (模块名, 期望说明, 期望主版本前缀)
EXPECTED = [
    ("torch", ">=2.5,<3", "2"),
    ("transformers", ">=4.57,<5", "4"),
    ("tokenizers", ">=0.22,<=0.23.0", "0.2"),
    ("sentence_transformers", ">=5.1,<6", "5"),
    ("modelscope", ">=1.40", "1"),
    ("datasets", ">=4.0,<=4.8.4", "4"),
    ("sklearn", ">=1.3", "1"),
    ("pandas", ">=2.1,<3", "2"),
]


def _ver(mod):
    try:
        m = importlib.import_module(mod)
        return getattr(m, "__version__", "?")
    except Exception as e:  # noqa: BLE001
        return f"MISSING ({type(e).__name__})"


def main() -> int:
    print("=" * 64)
    print("ai-skill-gap 环境体检")
    print(f"Python : {sys.version.split()[0]}  ({sys.executable})")
    total, used, free = shutil.disk_usage(ROOT)
    print(f"磁盘   : 项目盘剩余 {free / 1e9:.1f} GB")
    print("-" * 64)

    ok = True
    for mod, want, prefix in EXPECTED:
        v = _ver(mod)
        good = v.startswith(prefix)
        ok = ok and good
        print(f"[{'OK ' if good else 'BAD'}] {mod:<22} = {v:<18} (期望 {want})")

    try:
        import torch
        print(f"[info] torch.cuda.is_available() = {torch.cuda.is_available()}")
    except Exception:  # noqa: BLE001
        print("[info] torch 未安装或不可用")

    print("-" * 64)
    for d in ("models/hf_cache", "models/ms_cache", "models/uv_cache"):
        p = os.path.join(ROOT, d)
        print(f"[cache] {d:<18} exists={os.path.isdir(p)}")
    print("=" * 64)

    if not ok:
        print("!! 发现版本与锁矩阵不符（见上方 BAD 行），可能已触发 modelscope/transformers 冲突")
        return 1
    print("体检通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
