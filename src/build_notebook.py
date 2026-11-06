"""Generate notebooks/analysis.ipynb (story + code) and execute it in place.

Usage:  python src/build_notebook.py
"""
from pathlib import Path

import nbformat as nbf
from nbconvert.preprocessors import ExecutePreprocessor

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks" / "analysis.ipynb"

cells: list = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: cells.append(nbf.v4.new_code_cell(s.strip()))

md("""
# Olist marketplace: why customers don't come back, and what to fix first

**Business question.** Olist is a Brazilian marketplace connecting small sellers to customers.
Leadership believes *bad delivery experiences are killing repeat purchases*. Is that true?
And if not, where should the business spend its effort?

**Data.** Olist's public dataset: 99,441 orders, 9 relational tables, Sep 2016 to Oct 2018.
The analysis covers the **96,470 delivered orders** from **93,350 unique customers**.

**Approach.**
1. SQL (DuckDB) builds a clean order-level fact table and a customer dimension (`sql/01_build_model.sql`)
2. SQL answers each business question (`sql/02` to `07`), saved to `data/processed/`
3. This notebook adds statistical tests, impact sizing and the recommendations

> **Spoiler.** The hypothesis is only half right. Late delivery strongly damages **ratings**,
> but it does **not** measurably reduce **repeat purchases**. Repeat buying is ~2% no matter
> what happens. So the fixes are two separate programmes: an operations fix for lateness
> and a CRM fix for retention.
""")

code("""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
from IPython.display import Image, display

ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT / "src"))

import run_sql, charts
run_sql.main()            # rebuild the model and every SQL output from the raw CSVs
charts.build_all()        # re-render every figure

P = ROOT / "data" / "processed"
read = lambda name: pd.read_csv(P / f"{name}.csv")
fig = lambda name: display(Image(filename=str(ROOT / "reports" / "figures" / f"{name}.png"), width=760))
pd.set_option("display.float_format", "{:,.2f}".format)
""")

md("## 1. Data quality: what had to be fixed before trusting any number")
code("""display(read("dq_row_counts")); display(read("dq_issues"))""")
md("""
The two decisions that matter most:
* **`customer_unique_id` is the real person.** The raw `customer_id` changes with every order, so using it
  would make the repeat rate look like 0%.
* **Same-day orders are not loyalty.** 890 extra orders were placed on the same day as an earlier one
  (one basket split by seller). A *repeat customer* is someone who bought on **two different days**.
""")

md("## 2. Headline KPIs")
code("""read("kpi_headline").T.rename(columns={0: "value"})""")
md("""
* R$15.4M revenue, average order R$160, average rating 4.16 / 5
* **8.1% of orders arrive after the promised date**, even though the median order arrives **12 days early**
  (the promised dates are already generous)
* **Only 2.16% of customers ever buy a second time**, and they generate just 4.2% of revenue
""")

md("## 3. Does late delivery hurt customer satisfaction?")
code("""display(read("reviews_by_delivery_status")); fig("fig01_reviews_by_delay"); fig("fig02_negative_review_share")""")
code("""
f = pd.read_csv(P / "fact_orders.csv", usecols=["is_late", "review_score", "is_negative_review"]).dropna()
late, ontime = f[f.is_late == 1].review_score, f[f.is_late == 0].review_score
u = stats.mannwhitneyu(late, ontime)
neg_late, neg_on = f[f.is_late == 1].is_negative_review.mean(), f[f.is_late == 0].is_negative_review.mean()
excess_neg = (neg_late - neg_on) * (f.is_late == 1).sum()
print(f"Mann-Whitney U test, late vs on-time review scores: p {'< 0.001' if u.pvalue < 0.001 else f'= {u.pvalue:.3f}'}")
print(f"Negative-review rate: late {neg_late:.1%} vs on-time {neg_on:.1%}  ({neg_late/neg_on:.1f}x)")
print(f"Bad reviews attributable to lateness: ~{excess_neg:,.0f} = {excess_neg / f.is_negative_review.sum():.0%} of all 1-2 star reviews")
""")
code("""read("negative_review_themes")""")
md("""
**Finding 1: lateness is the #1 driver of bad reviews.**
Late orders are 8% of volume but 34% of all 1-2 star reviews. The damage grows with every day of delay
(4.0 stars on the promised day, 3.3 at 1-3 days late, 1.7 at 8+ days late). About 64% of negative
comments mention delivery ("não recebi" = *I didn't receive it*, "atraso" = *delay*).
""")

md("## 4. Where and when does lateness happen?")
code("""
m = read("kpi_monthly"); m["month"] = pd.to_datetime(m.purchase_month).dt.strftime("%Y-%m")
m["late_orders"] = (m.orders * m.late_rate_pct / 100).round()
peak = m[m.month.isin(["2017-11", "2018-02", "2018-03"])]
print(f"3 peak months = {peak.orders.sum() / m.orders.sum():.0%} of orders but "
      f"{peak.late_orders.sum() / m.late_orders.sum():.0%} of late deliveries")
fig("fig03_monthly_late_rate")
""")
code("""
p = read("seller_pareto")
for t in (50, 80):
    r = p[p.cum_pct_of_late_orders >= t].iloc[0]
    print(f"{int(r.seller_rank):>4} sellers ({r.pct_of_sellers:.1f}% of sellers) cause {t}% of late orders")
w = read("seller_watchlist")
print(f"Chronic-late watchlist: {len(w)} sellers (30+ orders, >=15% late) | {w.orders.sum():,} orders | {w.late_orders.sum():,.0f} late")
fig("fig04_seller_pareto")
""")
code("""display(read("route_performance").head(10)); fig("fig05_routes")""")
md("""
**Finding 2: lateness is concentrated, so it is fixable.**
* **Time:** three months (Nov 2017 Black Friday, Feb and Mar 2018) carry nearly half of all late deliveries.
  That is a capacity-planning failure in peaks, not a constant problem.
* **Sellers:** 3.5% of sellers cause half of all late orders.
* **Lanes:** long-haul lanes out of São Paulo (SP→RJ, SP→BA, SP→ES, SP→CE) run ~15% late, 2x the
  average. SP→RJ alone produces 16% of all late orders. The promised date doesn't adjust enough for distance.
""")

md("## 5. Does a bad experience stop customers coming back?")
code("""
c = pd.read_csv(P / "dim_customers.csv", parse_dates=["first_purchase_date"])
cw = c[c.first_purchase_date < "2018-03-01"].copy()      # everyone gets a full 180-day window

def chi(col):
    t = pd.crosstab(cw[col], cw.repeat_180d)
    return stats.chi2_contingency(t)[1]

cw["rating_band"] = pd.cut(cw.first_order_review, [0, 2, 3, 5], labels=["1-2", "3", "4-5"])
print(f"Repeat within 180 days, overall: {cw.repeat_180d.mean():.2%}  (n = {len(cw):,})")
for flag, g in cw.groupby("first_order_late"):
    print(f"  first order {'late   ' if flag else 'on time'}: {g.repeat_180d.mean():.2%} came back (n = {len(g):,})")
print(f"chi-square p (late vs on-time):     {chi('first_order_late'):.2f}  -> not significant")
print(f"chi-square p (first rating band):   {chi('rating_band'):.2f}  -> not significant")
fig("fig06_repeat_vs_experience")
""")
md("""
**Finding 3: the hypothesis is wrong.** Customers whose first order was late come back at 1.7% vs 2.0%;
1-star customers at 1.7% vs 2.0% for 5-star customers. Neither difference is statistically significant.
**Fixing delivery will improve ratings, but on its own it will not create repeat customers.**

So what *does* relate to repeat buying?
""")
code("""
top = cw.first_order_category.value_counts()
cats = cw[cw.first_order_category.isin(top[top >= 1000].index)]
p_cat = stats.chi2_contingency(pd.crosstab(cats.first_order_category, cats.repeat_180d))[1]
print(f"chi-square p (first-order category): {'< 0.001' if p_cat < 0.001 else round(p_cat, 3)}  -> significant")
display(read("repeat_by_first_category").head(6)); fig("fig07_repeat_by_category")
""")
code("""
# Can we predict who comes back from first-order information? (honest check)
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
X = pd.get_dummies(cw[["first_order_category", "customer_state", "first_payment_type"]].fillna("na"), drop_first=True)
X["late"] = cw.first_order_late; X["review"] = cw.first_order_review.fillna(cw.first_order_review.median())
X["log_value"] = np.log1p(cw.first_order_value.fillna(0))
auc = cross_val_score(LogisticRegression(max_iter=2000, class_weight="balanced"), X, cw.repeat_180d, cv=5, scoring="roc_auc")
print(f"5-fold ROC-AUC predicting repeat from first-order data: {auc.mean():.3f} (0.5 = coin flip)")
""")
md("""
**Finding 4: repeat buying is not something customers drift into; it has to be triggered.**
First-purchase category matters (fashion accessories 3.3%, bed/bath 2.7% vs cool-stuff 1.1%, p < 0.001),
but even a model using every first-order attribute barely beats a coin flip. Nothing in the first
experience strongly predicts return, which points to the missing piece: **there is no retention
programme pulling customers back.** And timing is clear: 76% of those who do return do so within 6 months.
""")
code("""display(read("days_to_second_purchase")); fig("fig08_days_to_second")""")

md("## 6. Who to target")
code("""display(read("customer_segments")); fig("fig09_segments")""")
md("""
* **New customers (last 120 days): 24,000 people, 26% of revenue.** This is the best second-order audience; they are inside the window when returns happen.
* **Dormant high-value: 16,000 people (17%) who generated 41% of revenue.** This is the win-back audience.
""")

md("## 7. Impact sizing (scenarios, with assumptions shown)")
code("""
k = read("kpi_headline").iloc[0]; r = read("retention_summary").iloc[0]
st = read("reviews_by_delivery_status").set_index("delivery_status")
neg_gap = (st.loc["Late", "negative_review_pct"] - st.loc["On time / early", "negative_review_pct"]) / 100
avg_late = k.late_rate_pct / 100

# A. Bring high-risk lanes (>=1.5x average, 500+ orders) down to the national average
lanes = read("route_performance"); hot = lanes[lanes.late_rate_pct >= 150 * avg_late]
a_late = (hot.late_orders - hot.orders * avg_late).sum()
# B. Bring the chronic-late seller watchlist down to the national average
w = read("seller_watchlist"); b_late = (w.late_orders - w.orders * avg_late).sum()
# C. Bring the 3 peak months down to the average of the other months
off = m[~m.month.isin(peak.month)]; off_rate = off.late_orders.sum() / off.orders.sum()
c_late = (peak.late_orders - peak.orders * off_rate).sum()

ops = pd.DataFrame({
    "lever": [f"A. Fix {len(hot)} high-risk lanes", f"B. Seller SLA for {len(w)} chronic sellers", "C. Peak-season capacity plan"],
    "late_orders_avoided": [a_late, b_late, c_late]})
ops["pct_of_all_late"] = ops.late_orders_avoided / (k.delivered_orders * avg_late) * 100
ops["bad_reviews_avoided"] = ops.late_orders_avoided * neg_gap
display(ops.round(0))
print("Levers overlap (a late SP->RJ order in March from a watchlist seller counts in all three), so do not add them up.")
""")
code("""
# D. Retention: second-order CRM programme
new_per_year = c[(c.first_purchase_date >= "2018-01-01") & (c.first_purchase_date < "2018-09-01")].shape[0] / 8 * 12
extra_value = r.avg_ltv_repeat - r.avg_ltv_one_time      # what a converted repeat customer adds
annual_rev = k.revenue_brl / 20 * 12                      # ~20 months of data
crm = pd.DataFrame({"repeat_uplift_pp": [0.5, 1.0, 2.0]})
crm["extra_repeat_customers"] = new_per_year * crm.repeat_uplift_pp / 100
crm["extra_revenue_brl"] = crm.extra_repeat_customers * extra_value
crm["pct_of_annual_revenue"] = crm.extra_revenue_brl / annual_rev * 100
print(f"New customers per year ~{new_per_year:,.0f} | value added per converted repeat customer R${extra_value:,.0f} | annual revenue ~R${annual_rev/1e6:.1f}M")
display(crm.round(1))
""")
md("""
Reading the scenarios honestly:
* **Operations levers** each remove roughly 7-31% of late orders and ~250 to ~1,100 bad reviews; the peak-season plan is the biggest single lever.
  Ratings are the marketplace's public reputation; the revenue effect via conversion can't be measured with
  this dataset and should be tracked after launch.
* **Retention**: +1 percentage point of repeat rate (2% → 3%, still below the 3.3% the best category
  already achieves organically) is worth about R$120K a year (~1.3% of revenue). That is modest per year but
  compounding, and cheap to test with email/app campaigns.
""")

md("""
## 8. Recommendations

| # | Recommendation | Owner | Evidence | How to measure |
|---|---|---|---|---|
| 1 | **Peak-season playbook:** add carrier capacity and extend promised dates on long-haul lanes for Black Friday and Feb-Mar | Operations | 3 months = ~half of all late orders | Late rate in peak months ≤ 8% |
| 2 | **Lane-aware delivery promise** for SP→RJ/BA/ES/CE: set the promised date from each lane's actual history | Product / Logistics | Long-haul lanes 2x late; promise not adjusted enough for distance | Late rate per lane; A/B test conversion impact of the new date |
| 3 | **Seller delivery SLA + watchlist:** monthly scorecard; coaching, then reduced search ranking for chronic-late sellers | Seller ops | 102 sellers = 50% of late orders | Watchlist late rate → national average in 2 quarters |
| 4 | **Second-order CRM programme** in days 7-120 after first purchase, led by high-repeat categories (fashion accessories, bed/bath, sports, decor) | Marketing / CRM | Repeat is ~2% regardless of experience; 76% of returns happen within 6 months | Holdout test: 180-day repeat rate, treatment vs control |
| 5 | **Win-back offer** for 16K dormant high-value customers | Marketing | 17% of customers, 41% of revenue | Reactivation rate vs holdout |

## 9. Limitations and next steps
* **Correlation, not causation.** Reviews and lateness are observational. The CRM uplift must be proven with a holdout test.
* **No traffic or conversion data**, so the revenue effect of better ratings can't be measured here.
* **Repeat rate is structurally low** for a marketplace of one-off purchases; benchmark against similar marketplaces before setting targets.
* **Next:** a late-delivery risk model at checkout (lane, seller, month, product size) so operations can intervene *before* the order is late.
""")

nb = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {"name": "python3", "display_name": "Python 3"}})
NB.parent.mkdir(parents=True, exist_ok=True)
ExecutePreprocessor(timeout=900, kernel_name="python3").preprocess(nb, {"metadata": {"path": str(NB.parent)}})
nbf.write(nb, NB)
print("written + executed:", NB)
