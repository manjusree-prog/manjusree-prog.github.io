"""Load the eight raw Olist CSV files into a local SQLite database (data/olist.db).

Usage (from the repository root):
    python scripts/load_to_sqlite.py
"""
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DB = ROOT / "data" / "olist.db"

TABLES = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}


def main() -> None:
    DB.unlink(missing_ok=True)
    with sqlite3.connect(DB) as con:
        for table, file in TABLES.items():
            df = pd.read_csv(RAW / file)
            df.to_sql(table, con, index=False)
            print(f"{table:22s} {len(df):>9,} rows")
        # indexes on the join keys keep the later queries fast
        con.executescript("""
            CREATE INDEX ix_orders_id      ON orders (order_id);
            CREATE INDEX ix_orders_cust    ON orders (customer_id);
            CREATE INDEX ix_items_order    ON order_items (order_id);
            CREATE INDEX ix_pay_order      ON order_payments (order_id);
            CREATE INDEX ix_reviews_order  ON order_reviews (order_id);
            CREATE INDEX ix_customers_id   ON customers (customer_id);
            CREATE INDEX ix_products_id    ON products (product_id);
            CREATE INDEX ix_cat_name       ON category_translation (product_category_name);
        """)
        con.executescript((ROOT / "sql" / "01_views.sql").read_text())
        con.executescript((ROOT / "sql" / "02_clean_layer.sql").read_text())
    print(f"Database written to {DB.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
