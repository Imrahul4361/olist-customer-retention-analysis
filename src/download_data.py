"""Download the public Olist dataset from Olist's official GitHub repository.

Source: https://github.com/olist/work-at-olist-data  (also on Kaggle:
"Brazilian E-Commerce Public Dataset by Olist", CC BY-NC-SA 4.0)

Usage:  python src/download_data.py
"""
from pathlib import Path
from urllib.request import urlretrieve

BASE = "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets/"
FILES = [
    "olist_orders_dataset.csv",
    "olist_customers_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
]

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        target = RAW / name
        if target.exists():
            print(f"exists   {name}")
            continue
        print(f"download {name}")
        urlretrieve(BASE + name, target)
    print("done ->", RAW)


if __name__ == "__main__":
    main()
