"""pytest 根配置：把项目根目录加入 sys.path，保证 `import src.*` 可用。"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
