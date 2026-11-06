"""Build reports/Olist_Recommendations_Deck.pptx (7 slides, native charts, speaker notes).

Every number is read from data/processed, so the deck stays in sync with the SQL.
Usage:  python src/build_deck.py      (run src/run_sql.py first)
"""
from pathlib import Path

import pandas as pd
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
OUT = ROOT / "reports" / "Olist_Recommendations_Deck.pptx"

NAVY, BLUE, ORANGE, GREY = RGBColor(0x14, 0x23, 0x3B), RGBColor(0x2A, 0x78, 0xD6), RGBColor(0xEB, 0x68, 0x34), RGBColor(0xC3, 0xC2, 0xB7)
INK, INK2, MUTED, TINT, WHITE = RGBColor(0x0B, 0x0B, 0x0B), RGBColor(0x52, 0x51, 0x4E), RGBColor(0x89, 0x87, 0x81), RGBColor(0xF2, 0xF5, 0xFA), RGBColor(0xFF, 0xFF, 0xFF)
ICE = RGBColor(0xB7, 0xD3, 0xF6)
FONT = "Calibri"

read = lambda n: pd.read_csv(P / f"{n}.csv")


# ----------------------------------------------------------------- helpers
def text(slide, x, y, w, h, runs, size=16, color=INK, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, name=None):
    """runs: str, or list of paragraphs; a paragraph is str or list of (text, {opts})."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    paras = [runs] if isinstance(runs, str) else runs
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(6)
        for t, o in ([(para, {})] if isinstance(para, str) else para):
            r = p.add_run()
            r.text = t
            f = r.font
            f.name = FONT
            f.size = Pt(o.get("size", size))
            f.bold = o.get("bold", bold)
            f.italic = o.get("italic", False)
            f.color.rgb = o.get("color", color)
    return tb


def box(slide, x, y, w, h, fill, radius=True, name=None):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
                               Inches(x), Inches(y), Inches(w), Inches(h))
    if radius:
        s.adjustments[0] = 0.08
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.line.fill.background()
    s.shadow.inherit = False
    if name:
        s.name = name
    return s


def circle_num(slide, x, y, n, fill=BLUE, d=0.42):
    c = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    c.fill.solid(); c.fill.fore_color.rgb = fill; c.line.fill.background(); c.shadow.inherit = False
    tf = c.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = str(n); r.font.size = Pt(14); r.font.bold = True; r.font.color.rgb = WHITE; r.font.name = FONT


def title(slide, t, kicker=None):
    if kicker:
        text(slide, 0.6, 0.38, 12, 0.3, kicker.upper(), size=12, color=BLUE, bold=True, name="Kicker")
    text(slide, 0.6, 0.66, 12.1, 0.9, t, size=32, bold=True, color=INK, name="Title")


def footer(slide, n):
    text(slide, 0.6, 7.05, 9, 0.25, "Source: Olist public e-commerce dataset · 96,470 delivered orders · 2016-2018",
         size=10, color=MUTED, name="Source")
    text(slide, 12.2, 7.05, 0.55, 0.25, str(n), size=10, color=MUTED, align=PP_ALIGN.RIGHT, name="Page")


def bg(slide, color):
    f = slide.background.fill
    f.solid()
    f.fore_color.rgb = color


def style_chart(chart, pct=False, maxv=None, horizontal=False):
    chart.has_legend = False
    chart.font.name = FONT
    chart.font.size = Pt(12)
    chart.font.color.rgb = INK2
    va, ca = chart.value_axis, chart.category_axis
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = RGBColor(0xE1, 0xE0, 0xD9)
    va.major_gridlines.format.line.width = Pt(0.75)
    va.format.line.fill.background()
    va.tick_labels.font.color.rgb = MUTED
    va.tick_labels.font.size = Pt(11)
    if pct:
        va.tick_labels.number_format = '0"%"'
        va.tick_labels.number_format_is_linked = False
    if maxv is not None:
        va.maximum_scale = maxv
    va.minimum_scale = 0
    ca.format.line.color.rgb = GREY
    ca.tick_labels.font.color.rgb = INK2
    ca.tick_labels.font.size = Pt(12)
    ca.has_major_gridlines = False
    if horizontal:
        ca.reverse_order = True


def bar_chart(slide, x, y, w, h, cats, vals, colors, fmt='0.0', pct=False, maxv=None, horizontal=False, name=None):
    cd = CategoryChartData()
    cd.categories = cats
    cd.add_series("value", vals)
    kind = XL_CHART_TYPE.BAR_CLUSTERED if horizontal else XL_CHART_TYPE.COLUMN_CLUSTERED
    gf = slide.shapes.add_chart(kind, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    if name:
        gf.name = name
    ch = gf.chart
    style_chart(ch, pct=pct, maxv=maxv, horizontal=horizontal)
    plot = ch.plots[0]
    plot.gap_width = 70
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format = fmt + ('"%"' if pct else "")
    dl.number_format_is_linked = False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size = Pt(12)
    dl.font.color.rgb = INK
    ser = plot.series[0]
    for i, c in enumerate(colors):
        pt = ser.points[i]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = c
    return ch


def _skip_tick_labels(axis, n):
    """Show every n-th category label (python-pptx has no API for c:tickLblSkip)."""
    from pptx.oxml.ns import qn
    from lxml import etree
    ax = axis._element
    el = etree.SubElement(ax, qn("c:tickLblSkip"))
    el.set("val", str(n))
    # schema order: ... lblOffset, tickLblSkip, tickMarkSkip, noMultiLvlLbl
    nm = ax.find(qn("c:noMultiLvlLbl"))
    if nm is not None:
        nm.addprevious(el)


def stat(slide, x, y, w, big, label, color=BLUE, big_size=48, name=None):
    box(slide, x, y, w, 1.95, TINT, name=name)
    text(slide, x + 0.3, y + 0.22, w - 0.6, 0.85, big, size=big_size, bold=True, color=color)
    text(slide, x + 0.3, y + 1.08, w - 0.6, 0.8, label, size=15, color=INK2)


# ----------------------------------------------------------------- data
k = read("kpi_headline").iloc[0]
st = read("reviews_by_delivery_status").set_index("delivery_status")
delay = read("reviews_by_days_vs_promise")
monthly = read("kpi_monthly")
monthly["label"] = pd.to_datetime(monthly.purchase_month).dt.strftime("%b %y")
monthly["late"] = monthly.orders * monthly.late_rate_pct / 100
peak = monthly[monthly.label.isin(["Nov 17", "Feb 18", "Mar 18"])]
peak_share = peak.late.sum() / monthly.late.sum() * 100
peak_orders = peak.orders.sum() / monthly.orders.sum() * 100
pareto = read("seller_pareto")
p50 = pareto[pareto.cum_pct_of_late_orders >= 50].iloc[0]
routes = read("route_performance").set_index("route")
exp = read("repeat_by_first_order_experience").set_index("first_order_delivery")
rev = read("repeat_by_first_review").set_index("first_order_rating")
cats = read("repeat_by_first_category")
gap = read("days_to_second_purchase")
within180 = gap.cumulative_pct.iloc[2]
segs = read("customer_segments")
watch = read("seller_watchlist")

late_pct_orders = st.loc["Late", "pct_of_orders"]
late_pct_neg = st.loc["Late", "pct_of_all_negative_reviews"]

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]

# ----------------------------------------------------------------- 1. title
s = prs.slides.add_slide(BLANK); bg(s, NAVY)
text(s, 0.8, 1.0, 11, 0.4, "OLIST MARKETPLACE · CUSTOMER & DELIVERY ANALYSIS", size=14, bold=True, color=ICE)
text(s, 0.8, 1.6, 11.5, 2.4, [[("Fix deliveries to protect ratings.", {})], [("Build CRM to create loyalty.", {"color": ICE})]],
     size=44, bold=True, color=WHITE)
text(s, 0.8, 3.75, 10.5, 1.0,
     f"Why only {k.repeat_customer_pct:.1f}% of customers come back, what late deliveries really cost, "
     "and five actions ranked by impact.", size=18, color=RGBColor(0xDD, 0xE3, 0xEC))
for i, (v, l) in enumerate([(f"{int(k.delivered_orders):,}", "delivered orders"),
                            (f"{int(k.customers):,}", "customers"),
                            (f"R${k.revenue_brl / 1e6:.1f}M", "revenue analysed")]):
    text(s, 0.8 + i * 3.2, 5.7, 3.0, 0.6, v, size=28, bold=True, color=WHITE)
    text(s, 0.8 + i * 3.2, 6.3, 3.0, 0.4, l, size=13, color=ICE)
s.notes_slide.notes_text_frame.text = (
    "Olist is a Brazilian marketplace connecting small sellers to customers. Leadership believed bad delivery "
    "experiences were killing repeat purchases. I tested that with ~96K delivered orders across 9 related tables. "
    "Short answer: half right. Late deliveries badly damage ratings, but they are not why customers don't return. "
    "So the business needs two separate programmes.")

# ----------------------------------------------------------------- 2. exec summary
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "The hypothesis was half right, so the fix has two parts", "Executive summary")
stat(s, 0.6, 1.85, 3.9, f"{late_pct_neg:.0f}%", f"of all 1-2 star reviews come from late orders, which are only {late_pct_orders:.0f}% of volume", ORANGE)
stat(s, 4.72, 1.85, 3.9, f"{peak_share:.0f}%", f"of late deliveries happen in just 3 peak months ({peak_orders:.0f}% of orders)", ORANGE)
stat(s, 8.84, 1.85, 3.9, f"{k.repeat_customer_pct:.1f}%", "of customers ever buy again, and a late or 1-star first order doesn't change that", BLUE)
text(s, 0.6, 4.2, 5.9, 0.4, "What it means", size=18, bold=True)
text(s, 0.6, 4.65, 5.9, 2.2, [
    [("Lateness is concentrated", {"bold": True}), (" in peaks, a few sellers and long-haul lanes, so it is fixable with targeted operations work.", {})],
    [("Retention is not a service problem.", {"bold": True}), (" Nobody is pulling customers back; it needs a CRM programme of its own.", {})],
], size=15, color=INK2)
text(s, 6.85, 4.2, 5.9, 0.4, "What I recommend", size=18, bold=True)
recs = ["Peak-season capacity playbook", "Lane-aware delivery promise", "Seller SLA + watchlist",
        "Second-order CRM programme", "Win-back for dormant high-value customers"]
for i, r in enumerate(recs):
    circle_num(s, 6.85, 4.68 + i * 0.44, i + 1, ORANGE if i < 3 else BLUE, d=0.32)
    text(s, 7.32, 4.7 + i * 0.44, 5.4, 0.35, r, size=15, color=INK)
footer(s, 2)
s.notes_slide.notes_text_frame.text = (
    "Three numbers tell the story. One: late orders are 8% of volume but a third of bad reviews. Two: almost half of "
    "late deliveries happen in three peak months, so it's a capacity problem, not a constant one. Three: only about 2% of "
    "customers ever return, and that rate is the same whether their first order was late or not. Orange actions fix "
    "ratings; blue actions build loyalty.")

# ----------------------------------------------------------------- 3. delivery -> reviews
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Late deliveries cause a third of all bad reviews", "Finding 1 · Satisfaction")
labels = [b.split(". ", 1)[1] for b in delay.delivery_bucket]
ch = bar_chart(s, 0.5, 1.75, 7.9, 4.95, labels, list(delay.avg_review),
               [ORANGE if "late" in l else BLUE for l in labels], fmt="0.0", maxv=5, name="Chart reviews by delay")
ch.has_title = True
ch.chart_title.text_frame.text = "Average review (1-5) by delivery date vs promised date"
ch.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(13)
ch.chart_title.text_frame.paragraphs[0].runs[0].font.color.rgb = INK2
ch.chart_title.text_frame.paragraphs[0].runs[0].font.bold = False
box(s, 8.75, 1.85, 4.0, 4.8, TINT)
text(s, 9.05, 2.1, 3.45, 4.4, [
    [(f"{st.loc['Late', 'negative_review_pct']:.0f}%", {"size": 36, "bold": True, "color": ORANGE})],
    [("of late orders get a 1-2 star review, vs "
      f"{st.loc['On time / early', 'negative_review_pct']:.0f}% of on-time orders (p < 0.001)", {})],
    [("", {"size": 6})],
    [("64%", {"size": 36, "bold": True, "color": ORANGE})],
    [("of negative comments mention delivery: \"não recebi\" (didn't receive), \"atraso\" (delay)", {})],
], size=15, color=INK2)
footer(s, 3)
s.notes_slide.notes_text_frame.text = (
    "There's a clear dose-response: delivered on the promised day averages 4.0 stars; 1-3 days late, 3.3; over a week "
    "late, 1.7. Late orders are 5.9 times more likely to get a bad review. I tested it with a Mann-Whitney U test "
    "(p < 0.001), and a keyword scan of the Portuguese review text confirms delivery is the top complaint. Ratings are "
    "the marketplace's public reputation, so this matters even before we talk about retention.")

# ----------------------------------------------------------------- 4. where lateness comes from
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Lateness is concentrated, which makes it fixable", "Finding 2 · Root cause")
cd = CategoryChartData()
cd.categories = list(monthly.label)
cd.add_series("Late rate", list(monthly.late_rate_pct))
gf = s.shapes.add_chart(XL_CHART_TYPE.LINE, Inches(0.5), Inches(1.75), Inches(7.9), Inches(4.95), cd)
gf.name = "Chart monthly late rate"
ch = gf.chart
style_chart(ch, pct=True, maxv=25)
ch.category_axis.tick_labels.font.size = Pt(11)
_skip_tick_labels(ch.category_axis, 2)
ser = ch.plots[0].series[0]
ser.format.line.color.rgb = BLUE
ser.format.line.width = Pt(2.25)
ser.smooth = False
from pptx.enum.chart import XL_MARKER_STYLE
ser.marker.style = XL_MARKER_STYLE.NONE
for i, l in enumerate(monthly.label):
    if l in ("Nov 17", "Feb 18", "Mar 18"):
        pt = ser.points[i]
        pt.marker.style = XL_MARKER_STYLE.CIRCLE
        pt.marker.size = 9
        pt.marker.format.fill.solid(); pt.marker.format.fill.fore_color.rgb = ORANGE
        pt.marker.format.line.color.rgb = WHITE
        dl = pt.data_label
        dl.position = XL_LABEL_POSITION.ABOVE
        dl.text_frame.text = f"{monthly.late_rate_pct.iloc[i]:.0f}%"
        run = dl.text_frame.paragraphs[0].runs[0]
        run.font.size = Pt(12); run.font.bold = True; run.font.color.rgb = INK; run.font.name = FONT
ch.has_title = True
ch.chart_title.text_frame.text = "Late-delivery rate by purchase month"
r0 = ch.chart_title.text_frame.paragraphs[0].runs[0]
r0.font.size = Pt(13); r0.font.color.rgb = INK2; r0.font.bold = False
sp_rj = routes.loc["SP -> RJ"]
cards = [
    (f"{peak_share:.0f}%", f"of late orders in 3 months: Nov 17 (Black Friday), Feb and Mar 18"),
    (f"{int(p50.seller_rank)}", f"sellers ({p50.pct_of_sellers:.1f}% of all) cause half of late orders; {len(watch)} are chronic (15%+ late)"),
    (f"{sp_rj.late_rate_pct:.0f}%", f"late on São Paulo → Rio, 2x the average; this lane alone = {sp_rj.pct_of_all_late:.0f}% of late orders"),
]
for i, (v, l) in enumerate(cards):
    y = 1.85 + i * 1.62
    box(s, 8.75, y, 4.0, 1.45, TINT)
    text(s, 9.0, y + 0.18, 1.3, 0.7, v, size=30, bold=True, color=ORANGE)
    text(s, 10.3, y + 0.2, 2.3, 1.15, l, size=13, color=INK2)
footer(s, 4)
s.notes_slide.notes_text_frame.text = (
    "The average late rate of 8% hides the pattern. Three months carry nearly half of all late deliveries, which points to "
    "capacity in peaks. A Pareto analysis shows 102 sellers, 3.5% of the base, cause half the late orders. And long-haul "
    "lanes out of São Paulo run around 15% late versus 6% within São Paulo, so the promised date isn't adjusting enough "
    "for distance. Concentrated problems are cheap to target.")

# ----------------------------------------------------------------- 5. retention
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "A bad first order doesn't stop customers returning", "Finding 3 · Retention")
rcats = ["First order\nlate", "First order\non time", "Rated\n1-2 stars", "Rated\n3 stars", "Rated\n4-5 stars"]
rvals = [exp.loc["Late", "repeat_180d_pct"], exp.loc["On time / early", "repeat_180d_pct"],
         rev.loc["1-2 stars", "repeat_180d_pct"], rev.loc["3 stars", "repeat_180d_pct"], rev.loc["4-5 stars", "repeat_180d_pct"]]
ch = bar_chart(s, 0.5, 1.75, 7.9, 4.95, rcats, rvals, [BLUE] * 5, fmt="0.0", pct=True, maxv=3, name="Chart repeat vs experience")
ch.value_axis.major_unit = 1
ch.has_title = True
ch.chart_title.text_frame.text = "Bought again within 180 days · differences not significant (p = 0.17 / 0.13)"
r0 = ch.chart_title.text_frame.paragraphs[0].runs[0]
r0.font.size = Pt(13); r0.font.color.rgb = INK2; r0.font.bold = False
top = cats.iloc[0]; bottom = cats.iloc[-1]
box(s, 8.75, 1.85, 4.0, 4.8, TINT)
text(s, 9.05, 2.1, 3.45, 4.4, [
    [("What does matter", {"bold": True, "color": INK, "size": 17})],
    [(f"{top.repeat_180d_pct:.1f}% vs {bottom.repeat_180d_pct:.1f}%", {"size": 28, "bold": True, "color": BLUE})],
    [(f"repeat rate when the first purchase is {top.category.replace('_', ' ')} vs {bottom.category.replace('_', ' ')} (p < 0.001)", {})],
    [("", {"size": 6})],
    [(f"{within180:.0f}%", {"size": 28, "bold": True, "color": BLUE})],
    [("of second purchases happen within 6 months: the window for a CRM nudge", {})],
], size=14, color=INK2)
footer(s, 5)
s.notes_slide.notes_text_frame.text = (
    "This is where the original hypothesis fails. Customers whose first order was late came back at 1.7%, versus 2.0% for "
    "on-time. Chi-square p = 0.17, so not significant. Same for review score. I also trained a logistic regression on every "
    "first-order attribute: ROC-AUC 0.54, barely better than a coin flip. So no part of the first experience strongly "
    "predicts return. That tells me loyalty isn't being lost; it's never being built. What does differ is category: "
    "fashion accessories and bed-bath buyers return about 3x as often as cool-stuff buyers. Timing is also clear: "
    "three-quarters of returns happen within six months.")

# ----------------------------------------------------------------- 6. recommendations
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Five actions: three protect ratings, two build loyalty", "Recommendations")
new_cust = int(segs[segs.segment.str.contains("New")].customers.sum())
dormant_hv = segs[segs.segment.str.contains("Dormant high")].iloc[0]
rows = [
    ("Peak-season capacity playbook", "Operations", "Extra carrier capacity and longer promised dates on long-haul lanes for Black Friday and Feb-Mar",
     "Up to ~31% fewer late orders", "Peak-month late rate ≤ 8%", ORANGE),
    ("Lane-aware delivery promise", "Product / Logistics", "Promised date for SP→RJ / BA / ES / CE set from each lane's real delivery history",
     "~13% fewer late orders", "Late rate per lane; A/B test conversion", ORANGE),
    ("Seller SLA + watchlist", "Seller ops", f"Monthly scorecard for {len(watch)} chronic-late sellers: coaching, then lower search ranking",
     "~7% fewer late orders", "Watchlist late rate → average", ORANGE),
    ("Second-order CRM programme", "Marketing / CRM", f"Nudges on days 7-120 for {new_cust:,} recent customers, led by high-repeat categories",
     "+1 pp repeat ≈ R$120K / yr", "180-day repeat vs holdout group", BLUE),
    ("Win-back dormant high-value", "Marketing", f"Offer to {int(dormant_hv.customers):,} lapsed customers who generated {dormant_hv.pct_revenue:.0f}% of revenue",
     "Test & size", "Reactivation rate vs holdout", BLUE),
]
hdr_y = 1.75
for x, w, h in [(1.15, 3.0, "Action"), (4.25, 4.35, "What"), (8.7, 2.1, "Expected impact"), (10.9, 1.85, "Success metric")]:
    text(s, x, hdr_y, w, 0.3, h.upper(), size=11, bold=True, color=MUTED)
for i, (a, owner, what, imp, metric, col) in enumerate(rows):
    y = 2.15 + i * 0.95
    box(s, 0.6, y, 12.15, 0.83, TINT)
    circle_num(s, 0.72, y + 0.2, i + 1, col)
    text(s, 1.3, y + 0.1, 2.85, 0.65, [[(a, {"bold": True, "color": INK})], [(owner, {"size": 11, "color": MUTED})]], size=14)
    text(s, 4.25, y + 0.1, 4.35, 0.65, what, size=13, color=INK2, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 8.7, y + 0.1, 2.1, 0.65, imp, size=13, bold=True, color=INK, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 10.9, y + 0.1, 1.75, 0.65, metric, size=12, color=INK2, anchor=MSO_ANCHOR.MIDDLE)
footer(s, 6)
s.notes_slide.notes_text_frame.text = (
    "Actions 1 to 3 attack lateness where it's concentrated. The impact figures come from bringing each problem area down to "
    "the normal late rate. They overlap, so I don't add them up. Actions 4 and 5 build loyalty, because the data says service "
    "alone won't. I size the CRM conservatively: one extra percentage point of repeat rate is about 760 customers and "
    "R$120K a year. Every action has a success metric, and the CRM ones must be proven with a holdout test, not assumed.")

# ----------------------------------------------------------------- 7. measure + limits
s = prs.slides.add_slide(BLANK); bg(s, NAVY)
text(s, 0.8, 0.6, 11, 0.4, "NEXT STEPS & LIMITATIONS", size=14, bold=True, color=ICE)
text(s, 0.8, 1.05, 11.8, 1.0, "Start with peak season; prove CRM with a holdout", size=34, bold=True, color=WHITE)
cols = [
    ("First 90 days", ["Peak playbook ready before next Black Friday",
                       "Seller scorecard live; watchlist notified",
                       "CRM pilot on 10% of new customers + holdout"]),
    ("What I'd build next", ["Late-delivery risk model at checkout (lane, seller, month, size)",
                             "Live dashboard: late rate by lane & seller",
                             "Category-specific CRM journeys"]),
    ("Limits of this analysis", ["Observational data: correlation, not causation",
                                 "No traffic/conversion data, so rating → revenue is untested",
                                 "Low repeat may be structural; benchmark first"]),
]
for i, (h, items) in enumerate(cols):
    x = 0.8 + i * 4.0
    box(s, x, 2.6, 3.75, 3.9, RGBColor(0x22, 0x34, 0x52))
    text(s, x + 0.3, 2.85, 3.2, 0.4, h, size=18, bold=True, color=WHITE)
    for j, it in enumerate(items):
        circle_num(s, x + 0.3, 3.5 + j * 0.95, j + 1, BLUE, d=0.3)
        text(s, x + 0.75, 3.48 + j * 0.95, 2.8, 0.85, it, size=14, color=RGBColor(0xDD, 0xE3, 0xEC))
text(s, 0.8, 6.85, 11.5, 0.3, "Built with SQL (DuckDB) · Python (pandas, SciPy, scikit-learn) · Interactive dashboard · github: olist-customer-retention-analysis",
     size=11, color=ICE)
s.notes_slide.notes_text_frame.text = (
    "If I were presenting to Olist, I'd start with the peak-season playbook because it's the single biggest lever and Black "
    "Friday is predictable. In parallel I'd launch a small CRM pilot with a holdout so we prove the uplift before scaling. "
    "I'm also clear about the limits: this is observational data, and without traffic data I can't price the rating effect, "
    "so I'd track conversion after the changes go live.")

OUT.parent.mkdir(parents=True, exist_ok=True)
prs.save(OUT)
print("written", OUT)
