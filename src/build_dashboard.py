"""Build dashboard/index.html by embedding the SQL outputs into dashboard/template.html.

The page is a single self-contained file (Chart.js from a CDN), so it can be
opened locally or hosted for free on GitHub Pages.

Usage:  python src/build_dashboard.py      (run src/run_sql.py first)
"""
from datetime import date
import json
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
DASH = ROOT / "dashboard"


def read(name: str) -> pd.DataFrame:
    return pd.read_csv(P / f"{name}.csv")


def main() -> None:
    fact = (P / "fact_orders.csv").as_posix()
    monthly_q = f"""
        SELECT strftime(purchase_month, '%Y-%m') AS month, {{dim}}
               COUNT(*) AS orders, ROUND(SUM(order_value), 0) AS revenue, SUM(is_late) AS late,
               COUNT(review_score) AS reviews, ROUND(SUM(review_score), 1) AS review_sum,
               SUM(CASE WHEN review_score <= 2 THEN 1 ELSE 0 END) AS negative
        FROM read_csv_auto('{fact}')
        WHERE purchase_month BETWEEN '2017-01-01' AND '2018-08-01'
        GROUP BY ALL ORDER BY ALL"""
    con = duckdb.connect()
    monthly_all = con.execute(monthly_q.format(dim="")).df()
    monthly_state = con.execute(monthly_q.format(dim="customer_state,")).df()
    states = (monthly_state.groupby("customer_state").orders.sum()
              .sort_values(ascending=False).index.tolist())

    pareto = read("seller_pareto")
    # thin the 2,948-point curve to ~150 points for the browser
    step = max(1, len(pareto) // 150)
    pareto = pd.concat([pareto.iloc[::step], pareto.iloc[[-1]]]).drop_duplicates()

    delay = read("reviews_by_days_vs_promise")
    # two-line axis labels, e.g. ["10+ days", "early"]
    delay["label"] = [b.split(". ", 1)[1].rsplit(" ", 1) for b in delay.delivery_bucket]

    exp = read("repeat_by_first_order_experience")
    rev = read("repeat_by_first_review")
    repeat_exp = (
        [{"label": ["First order", "late" if r.first_order_delivery == "Late" else "on time"],
          "pct": r.repeat_180d_pct, "n": int(r.customers)}
         for r in exp.itertuples()]
        + [{"label": ["Rated", r.first_order_rating], "pct": r.repeat_180d_pct, "n": int(r.customers)}
           for r in rev.itertuples()]
    )

    cats = read("repeat_by_first_category")
    segs = read("customer_segments")
    segs["segment"] = segs.segment.str.split(". ", n=1).str[1]

    data = {
        "generated": date.today().isoformat(),
        "kpi": read("kpi_headline").iloc[0].to_dict(),
        "monthly_all": monthly_all.to_dict("records"),
        "monthly_state": monthly_state.to_dict("records"),
        "states": states,
        "delay": delay[["label", "orders", "avg_review", "negative_review_pct"]].to_dict("records"),
        "pareto": [{"x": round(r.pct_of_sellers, 1), "y": round(r.cum_pct_of_late_orders, 1)} for r in pareto.itertuples()],
        "routes": read("route_performance").nlargest(10, "orders").sort_values("late_rate_pct", ascending=False)
                    [["route", "orders", "late_rate_pct", "avg_delivery_days"]].to_dict("records"),
        "repeat_exp": repeat_exp,
        "categories": cats[["category", "customers", "repeat_180d_pct"]].to_dict("records"),
        "cat_avg": round(cats.came_back_180d.sum() / cats.customers.sum() * 100, 2),
        "segments": segs[["segment", "customers", "pct_customers", "pct_revenue"]].to_dict("records"),
    }
    html = (DASH / "template.html").read_text(encoding="utf-8")
    payload = json.dumps(data, default=float, separators=(",", ":")).replace("</", "<\\/")
    (DASH / "index.html").write_text(html.replace("/*DATA*/null", payload), encoding="utf-8")
    print("written", DASH / "index.html", f"({len(payload) / 1024:.0f} KB data)")


if __name__ == "__main__":
    main()
