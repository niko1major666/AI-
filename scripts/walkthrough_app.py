"""用 AppTest 无头走一遍三页面，打印各页实际渲染内容。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from streamlit.testing.v1 import AppTest

APP = ROOT / "src" / "app" / "app.py"
at = AppTest.from_file(str(APP), default_timeout=60)
at.run()
print("EXCEPTIONS:", at.exception)

print("\n===== 页面1：技能图谱（默认）=====")
for m in at.metric:
    print(f"  metric: {m.label} = {m.value}")
print("  header:", [h.value for h in at.header])

at.sidebar.radio[0].set_value("简历匹配")
at.run()
print("\n===== 页面2：简历匹配 =====")
at.text_area[0].set_value("熟悉 Python、Pandas、NumPy；做过桥梁健康监测数据分析；会用 CAD、BIM")
at.button[0].click()
at.run()
for md in at.markdown:
    print("  md:", md.value)
for c in at.caption:
    print("  caption:", c.value)

at.sidebar.radio[0].set_value("差距报告")
at.run()
print("\n===== 页面3：差距报告 =====")
sel = at.selectbox[0]
print("  可选岗位数:", len(sel.options))
sel.set_value(sel.options[0])
at.text_input[0].set_value("Python, Pandas")
at.button[0].click()
at.run()
for m in at.metric:
    print(f"  metric: {m.label} = {m.value}")
for e in at.expander:
    print("  expander:", e.label)
