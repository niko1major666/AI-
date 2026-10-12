from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "src" / "app" / "app.py"


def test_app_runs_without_exception():
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    assert not at.exception, f"app exceptions: {at.exception}"
