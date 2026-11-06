"""Chart functions used by the notebook, README and slide deck.

One consistent visual system:
  * BLUE   = the measure being shown
  * ORANGE = the highlighted problem (late deliveries, the "so what")
  * GREY   = context / de-emphasised
Hairline grids, no chart junk, values labelled selectively.
Every function reads a CSV from data/processed and writes a PNG to
reports/figures.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
FIG = ROOT / "reports" / "figures"

BLUE, ORANGE, GREY = "#2a78d6", "#eb6834", "#c3c2b7"
INK, INK2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#fcfcfb"

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"],
    "font.size": 11,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": GREY,
    "axes.labelcolor": INK2,
    "axes.titlecolor": INK,
    "axes.titlesize": 14,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.titlepad": 26,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.labelcolor": INK2,
    "ytick.labelcolor": INK2,
    "savefig.dpi": 160,
    "savefig.bbox": "tight",
})


def _read(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA / f"{name}.csv")


def _subtitle(ax, text: str) -> None:
    ax.text(0, 1.02, text, transform=ax.transAxes, color=INK2, fontsize=10.5, va="bottom")


def _save(fig, name: str) -> Path:
    FIG.mkdir(parents=True, exist_ok=True)
    path = FIG / f"{name}.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def _source(fig) -> None:
    fig.text(0.01, -0.02, "Source: Olist public e-commerce dataset, 96,470 delivered orders (2016-2018)",
             color=MUTED, fontsize=8.5)


# ---------------------------------------------------------------------------
def fig_reviews_by_delay():
    df = _read("reviews_by_days_vs_promise")
    labels = [b.split(". ", 1)[1] for b in df.delivery_bucket]
    colors = [ORANGE if "late" in l else BLUE for l in labels]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    bars = ax.bar(labels, df.avg_review, color=colors, width=0.55, zorder=2)
    for b, v in zip(bars, df.avg_review):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.06, f"{v:.1f}", ha="center", color=INK, fontsize=10.5)
    ax.set_ylim(0, 5)
    ax.set_ylabel("Average review (1-5 stars)")
    ax.grid(axis="x", visible=False)
    ax.set_title("Every extra day late costs stars")
    _subtitle(ax, "Average review score by delivery date vs the date promised at checkout")
    _source(fig)
    return _save(fig, "fig01_reviews_by_delay")


def fig_negative_review_share():
    df = _read("reviews_by_delivery_status").set_index("delivery_status")
    late_orders = df.loc["Late", "pct_of_orders"]
    late_neg = df.loc["Late", "pct_of_all_negative_reviews"]
    fig, ax = plt.subplots(figsize=(9, 2.8))
    rows = ["Share of orders", "Share of 1-2 star reviews"]
    late = [late_orders, late_neg]
    for i, (r, v) in enumerate(zip(rows, late)):
        ax.barh(i, v, color=ORANGE, height=0.5, zorder=2)
        ax.barh(i, 100 - v, left=v + 0.4, color=GREY, height=0.5, zorder=2)
        if v >= 15:
            ax.text(v - 1, i, f"Late {v:.0f}%", ha="right", va="center", color="white", fontsize=10.5, weight="bold")
        else:
            ax.text(v + 1.5, i, f"Late {v:.0f}%", ha="left", va="center", color=INK, fontsize=10.5, weight="bold")
    ax.set_yticks(range(2), rows)
    ax.invert_yaxis()
    ax.set_xlim(0, 100.5)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter())
    ax.grid(False)
    ax.spines["left"].set_visible(False)
    ax.set_title("8% of orders cause a third of all bad reviews")
    _subtitle(ax, "Late deliveries (orange) vs on-time / early deliveries (grey)")
    _source(fig)
    return _save(fig, "fig02_negative_review_share")


def fig_monthly_late_rate():
    df = _read("kpi_monthly")
    df["m"] = pd.to_datetime(df.purchase_month)
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.plot(df.m, df.late_rate_pct, color=BLUE, lw=2, zorder=3)
    ax.fill_between(df.m, df.late_rate_pct, color=BLUE, alpha=0.08, zorder=2)
    avg = (df.late_rate_pct * df.orders).sum() / df.orders.sum()
    ax.axhline(avg, color=MUTED, lw=1, zorder=1)
    ax.text(df.m.iloc[0], avg + 0.6, f"average {avg:.1f}%", color=INK2, fontsize=9.5)
    peaks = df.nlargest(3, "late_rate_pct")
    ax.scatter(peaks.m, peaks.late_rate_pct, s=70, color=ORANGE, edgecolor=SURFACE, linewidth=2, zorder=4)
    for _, r in peaks.iterrows():
        left = r.m.month == 11  # Nov label sits left of its point so it can't collide with Feb
        ax.text(r.m - pd.Timedelta(days=12) if left else r.m, r.late_rate_pct + (0 if left else 1.0),
                f"{r.m:%b %y}: {r.late_rate_pct:.0f}%", ha="right" if left else "center",
                va="center" if left else "bottom", fontsize=9.5, color=INK)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_ylim(0, 25)
    ax.set_ylabel("Orders delivered late")
    ax.set_title("Lateness is a peak-season problem, not a constant one")
    _subtitle(ax, "Late-delivery rate by purchase month (orange = 3 worst months)")
    _source(fig)
    return _save(fig, "fig03_monthly_late_rate")


def fig_seller_pareto():
    df = _read("seller_pareto")
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.plot(df.pct_of_sellers, df.cum_pct_of_late_orders, color=BLUE, lw=2, zorder=3)
    for target in (50, 80):
        r = df[df.cum_pct_of_late_orders >= target].iloc[0]
        ax.plot([r.pct_of_sellers, r.pct_of_sellers], [0, target], color=MUTED, lw=1, zorder=1)
        ax.plot([0, r.pct_of_sellers], [target, target], color=MUTED, lw=1, zorder=1)
        ax.scatter([r.pct_of_sellers], [target], s=70, color=ORANGE, edgecolor=SURFACE, linewidth=2, zorder=4)
        ax.text(22, target - 1.5,
                f"{int(r.seller_rank)} sellers ({r.pct_of_sellers:.1f}%) = {target}% of late orders",
                fontsize=10, color=INK)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 102)
    ax.set_xlabel("Sellers, ranked by number of late orders")
    ax.set_ylabel("Cumulative share of late orders")
    ax.set_title("A small group of sellers causes most late deliveries")
    _subtitle(ax, "Pareto curve of late orders across 2,948 sellers")
    _source(fig)
    return _save(fig, "fig04_seller_pareto")


def fig_routes():
    df = _read("route_performance").nlargest(10, "orders").sort_values("late_rate_pct")
    avg = _read("kpi_headline").late_rate_pct.iloc[0]
    colors = [ORANGE if v >= 1.5 * avg else BLUE for v in df.late_rate_pct]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    bars = ax.barh(df.route, df.late_rate_pct, color=colors, height=0.55, zorder=2)
    for b, v, n in zip(bars, df.late_rate_pct, df.orders):
        ax.text(v + 0.25, b.get_y() + b.get_height() / 2, f"{v:.1f}%  ({n:,} orders)", va="center", fontsize=9.5, color=INK2)
    ax.axvline(avg, color=MUTED, lw=1, zorder=1)
    ax.text(avg + 0.2, -0.75, f"national avg {avg:.1f}%", fontsize=9.5, color=INK2)
    ax.xaxis.set_major_locator(mtick.MultipleLocator(5))
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_xlim(0, 22)
    ax.grid(axis="y", visible=False)
    ax.set_title("Long-haul lanes out of Sao Paulo run 2x the late rate")
    _subtitle(ax, "Late-delivery rate on the 10 busiest seller-state -> customer-state lanes (orange = 1.5x+ average)")
    _source(fig)
    return _save(fig, "fig05_routes")


def fig_repeat_vs_experience():
    a = _read("repeat_by_first_order_experience")
    b = _read("repeat_by_first_review")
    labels = list(a.first_order_delivery) + list(b.first_order_rating)
    vals = list(a.repeat_180d_pct) + list(b.repeat_180d_pct)
    fig, ax = plt.subplots(figsize=(9, 4.2))
    x = [0, 1, 2.6, 3.6, 4.6]
    bars = ax.bar(x, vals, color=BLUE, width=0.55, zorder=2)
    for xi, v in zip(x, vals):
        ax.text(xi, v + 0.06, f"{v:.1f}%", ha="center", fontsize=10.5, color=INK)
    ax.set_xticks(x, labels)
    ax.text(0.5, 2.75, "By first-order delivery", ha="center", color=INK2, fontsize=10.5, weight="bold")
    ax.text(3.6, 2.75, "By first-order rating", ha="center", color=INK2, fontsize=10.5, weight="bold")
    ax.axvline(1.8, color=GRID, lw=1)
    ax.set_ylim(0, 3)
    ax.yaxis.set_major_locator(mtick.MultipleLocator(0.5))
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=1))
    ax.set_ylabel("Bought again within 180 days")
    ax.grid(axis="x", visible=False)
    ax.set_title("A bad first experience barely changes whether people return")
    _subtitle(ax, "Repeat rate is ~2% whatever happens - differences are not statistically significant")
    _source(fig)
    return _save(fig, "fig06_repeat_vs_experience")


def fig_repeat_by_category():
    df = _read("repeat_by_first_category").sort_values("repeat_180d_pct")
    overall = df.came_back_180d.sum() / df.customers.sum() * 100
    colors = [BLUE if v > overall else GREY for v in df.repeat_180d_pct]
    fig, ax = plt.subplots(figsize=(9, 5.6))
    bars = ax.barh(df.category.str.replace("_", " "), df.repeat_180d_pct, color=colors, height=0.6, zorder=2)
    for b, v in zip(bars, df.repeat_180d_pct):
        ax.text(v + 0.04, b.get_y() + b.get_height() / 2, f"{v:.1f}%", va="center", fontsize=9.5, color=INK2)
    ax.axvline(overall, color=MUTED, lw=1, zorder=1)
    ax.text(overall + 0.04, -0.9, f"avg {overall:.1f}%", fontsize=9.5, color=INK2)
    ax.xaxis.set_major_locator(mtick.MultipleLocator(0.5))
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=1))
    ax.grid(axis="y", visible=False)
    ax.set_title("What people buy first predicts loyalty better than service does")
    _subtitle(ax, "180-day repeat rate by category of first purchase (blue = above average)")
    _source(fig)
    return _save(fig, "fig07_repeat_by_category")


def fig_days_to_second():
    df = _read("days_to_second_purchase")
    labels = [b.split(". ", 1)[1] for b in df.gap_bucket]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    colors = [BLUE if i < 3 else GREY for i in range(len(df))]
    bars = ax.bar(labels, df.pct, color=colors, width=0.55, zorder=2)
    for b, v, c in zip(bars, df.pct, df.cumulative_pct):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.6, f"{v:.0f}%", ha="center", fontsize=10.5, color=INK)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_ylim(0, 35)
    ax.set_ylabel("Share of repeat customers")
    ax.grid(axis="x", visible=False)
    ax.set_title("76% of second purchases happen within 6 months")
    _subtitle(ax, "Days between a customer's 1st and 2nd purchase day (blue = the CRM window)")
    _source(fig)
    return _save(fig, "fig08_days_to_second")


def fig_segments():
    df = _read("customer_segments")
    labels = [s.split(". ", 1)[1] for s in df.segment][::-1]
    cust = list(df.pct_customers)[::-1]
    rev = list(df.pct_revenue)[::-1]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    y = range(len(labels))
    ax.barh([i + 0.18 for i in y], cust, height=0.34, color=GREY, label="% of customers", zorder=2)
    ax.barh([i - 0.18 for i in y], rev, height=0.34, color=BLUE, label="% of revenue", zorder=2)
    for i, (c, r) in enumerate(zip(cust, rev)):
        ax.text(r + 0.6, i - 0.18, f"{r:.0f}%", va="center", fontsize=9.5, color=INK2)
        ax.text(c + 0.6, i + 0.18, f"{c:.0f}%", va="center", fontsize=9.5, color=MUTED)
    ax.set_yticks(list(y), labels)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, 62)
    ax.legend(loc="upper right", frameon=False, labelcolor=INK2)
    ax.set_title("Who to target: customer segments by recency and value")
    _subtitle(ax, "Share of customers vs share of revenue per segment")
    _source(fig)
    return _save(fig, "fig09_segments")


ALL = [fig_reviews_by_delay, fig_negative_review_share, fig_monthly_late_rate, fig_seller_pareto,
       fig_routes, fig_repeat_vs_experience, fig_repeat_by_category, fig_days_to_second, fig_segments]


def build_all() -> list[Path]:
    return [f() for f in ALL]


if __name__ == "__main__":
    for p in build_all():
        print(p.name)
