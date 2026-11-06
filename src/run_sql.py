"""Build the DuckDB analytical model and run every analysis query.

1. Loads the 8 raw CSVs into data/olist.duckdb as raw_* tables
2. Runs sql/01_build_model.sql  (fact_orders, dim_customers)
3. Runs every "-- name: <query>" block in sql/02..07 and saves the
   result to data/processed/<query>.csv  (these CSVs feed the notebook,
   the HTML dashboard and the Power BI report)

Usage:  python src/run_sql.py
"""
from pathlib import Path
import re

import duckdb

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
SQL = ROOT / "sql"
DB = ROOT / "data" / "olist.duckdb"

RAW_TABLES = {
    "raw_orders": "olist_orders_dataset.csv",
    "raw_customers": "olist_customers_dataset.csv",
    "raw_items": "olist_order_items_dataset.csv",
    "raw_payments": "olist_order_payments_dataset.csv",
    "raw_reviews": "olist_order_reviews_dataset.csv",
    "raw_products": "olist_products_dataset.csv",
    "raw_sellers": "olist_sellers_dataset.csv",
    "raw_category_translation": "product_category_name_translation.csv",
}


def connect() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DB))


def load_raw(con: duckdb.DuckDBPyConnection) -> None:
    for table, file in RAW_TABLES.items():
        path = (RAW / file).as_posix()
        con.execute(
            f"CREATE OR REPLACE TABLE {table} AS "
            f"SELECT * FROM read_csv_auto('{path}', header=true)"
        )


def named_queries(sql_text: str) -> list[tuple[str, str]]:
    """Split a .sql file into (name, query) pairs on '-- name:' markers."""
    parts = re.split(r"^--\s*name:\s*(\w+)\s*$", sql_text, flags=re.M)
    return [(parts[i], parts[i + 1].strip().rstrip(";")) for i in range(1, len(parts), 2)]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    con = connect()
    print("loading raw CSVs ...")
    load_raw(con)

    print("building model (01_build_model.sql) ...")
    con.execute((SQL / "01_build_model.sql").read_text(encoding="utf-8"))

    for sql_file in sorted(SQL.glob("0[2-9]_*.sql")):
        for name, query in named_queries(sql_file.read_text(encoding="utf-8")):
            df = con.execute(query).df()
            df.to_csv(OUT / f"{name}.csv", index=False)
            print(f"  {sql_file.name:28s} -> {name}.csv ({len(df)} rows)")

    # Clean order-level extract for Power BI / Tableau (no free text)
    con.execute(
        f"COPY (SELECT * EXCLUDE (review_text) FROM fact_orders ORDER BY purchased_at, order_id) "
        f"TO '{(OUT / 'fact_orders.csv').as_posix()}' (HEADER)"
    )
    con.execute(
        f"COPY (SELECT * FROM dim_customers ORDER BY first_purchase_date, customer_id) "
        f"TO '{(OUT / 'dim_customers.csv').as_posix()}' (HEADER)"
    )
    print("  exported fact_orders.csv, dim_customers.csv")
    con.close()


if __name__ == "__main__":
    main()
