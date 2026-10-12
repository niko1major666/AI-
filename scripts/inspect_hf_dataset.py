"""探查 HF 数据集结构：打印列名 + 前几行（streaming，不全量下载）。"""
import sys

from datasets import load_dataset

ds_id = sys.argv[1]
config = sys.argv[2] if len(sys.argv) > 2 else None

try:
    ds = load_dataset(ds_id, config, streaming=True) if config else load_dataset(ds_id, streaming=True)
    split = list(ds.keys())[0]
    it = iter(ds[split])
    for i in range(3):
        row = next(it)
        print(f"--- row {i} ---")
        for k, v in row.items():
            print(f"  {k}: {str(v)[:250]}")
except Exception as e:  # noqa: BLE001
    print("ERROR:", type(e).__name__, e)
