"""Insert docs/dashboard_data.json into dashboard/template.html and write
docs/index.html (served by GitHub Pages).

Usage (from the repository root):
    python scripts/build_dashboard.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
data = (ROOT / "docs" / "dashboard_data.json").read_text()
html = (ROOT / "dashboard" / "template.html").read_text().replace("/*DATA*/null", data)
(ROOT / "docs" / "index.html").write_text(html)
print("docs/index.html written")
