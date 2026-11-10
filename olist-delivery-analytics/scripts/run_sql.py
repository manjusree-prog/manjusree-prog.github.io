"""Run every named query in sql/03_*.sql and sql/04_*.sql and save each result
as a CSV in outputs/sql_results/.

A query starts with a line '-- name: <query_name>' and ends at the next one.

Usage (from the repository root):
    python scripts/run_sql.py
"""
import re
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "olist.db"
OUT = ROOT / "outputs" / "sql_results"
SQL_FILES = ["03_data_quality_checks.sql", "04_kpis.sql"]


def named_queries(text: str):
    parts = re.split(r"^-- name: (\w+)\s*$", text, flags=re.M)
    # parts = [preamble, name1, body1, name2, body2, ...]
    for name, body in zip(parts[1::2], parts[2::2]):
        yield name, body.strip().rstrip(";")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB) as con:
        for file in SQL_FILES:
            for name, query in named_queries((ROOT / "sql" / file).read_text()):
                df = pd.read_sql_query(query, con)
                df.to_csv(OUT / f"{name}.csv", index=False)
                print(f"{name:28s} {len(df):>5} rows")


if __name__ == "__main__":
    main()
