"""Generate the Power BI project (PBIP) in powerbi/.

    python src/build_powerbi.py        (run src/run_sql.py first)

Open powerbi/Olist.pbip in Power BI Desktop, click Home > Refresh once to
load the CSVs, then File > Save as > .pbix if you want a single file.

Structure follows Microsoft's PBIP format (TMDL semantic model +
report.json), modelled on microsoft/fabric-samples:
    Olist.pbip
    Olist.SemanticModel/definition/*.tmdl     data model + DAX measures
    Olist.Report/report.json                  3 report pages
"""
from pathlib import Path
import hashlib
import json
import shutil
import uuid

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "powerbi"
DATA = ROOT / "data" / "processed"
THEME_SRC = ROOT / "src" / "pbi_assets" / "CY25SU12.json"
T = "\t"


def uid(seed: str) -> str:
    """Deterministic GUID so regenerating doesn't create noisy diffs."""
    return str(uuid.UUID(hashlib.md5(seed.encode()).hexdigest()))


def hexname(seed: str) -> str:
    return hashlib.md5(seed.encode()).hexdigest()[:20]


# =====================================================================
# 1. SEMANTIC MODEL (TMDL)
# =====================================================================
def csv_m(file: str, types: list[tuple[str, str]], extra: str = "", rows_filter: str = "") -> str:
    """Power Query M that loads one CSV and sets column types."""
    type_list = ", ".join(f'{{"{c}", {t}}}' for c, t in types)
    steps = [
        f'Source = Csv.Document(File.Contents(DataFolder & "{file}"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv])',
        "Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true])",
        f'Typed = Table.TransformColumnTypes(Promoted, {{{type_list}}}, "en-US")',
    ]
    last = "Typed"
    if rows_filter:
        steps.append(f"Filtered = Table.SelectRows({last}, each {rows_filter})")
        last = "Filtered"
    for line in [l for l in extra.strip().split("\n") if l.strip()]:
        name = line.split("=", 1)[0].strip()
        steps.append(line.strip().replace("{prev}", last))
        last = name
    body = ",\n".join(f"    {s}" for s in steps)
    return f"let\n{body}\nin\n    {last}"


def indent(text: str, tabs: int) -> str:
    return "\n".join(T * tabs + line for line in text.split("\n"))


def col(name: str, dtype: str, fmt: str | None = None, summarize: str = "none", sort_by: str | None = None, hidden=False) -> str:
    q = f"'{name}'" if " " in name else name
    lines = [f"{T}column {q}", f"{T}{T}dataType: {dtype}"]
    if fmt:
        lines.append(f"{T}{T}formatString: {fmt}")
    if hidden:
        lines.append(f"{T}{T}isHidden")
    lines += [f"{T}{T}lineageTag: {uid('col' + name + dtype)}", f"{T}{T}summarizeBy: {summarize}", f"{T}{T}sourceColumn: {name}"]
    if sort_by:
        lines.append(f"{T}{T}sortByColumn: '{sort_by}'")
    lines += ["", f"{T}{T}annotation SummarizationSetBy = Automatic", ""]
    return "\n".join(lines)


def measure(name: str, dax: str, fmt: str, folder: str | None = None) -> str:
    lines = [f"{T}measure '{name}' = {dax}", f"{T}{T}formatString: {fmt}"]
    if folder:
        lines.append(f"{T}{T}displayFolder: {folder}")
    lines += [f"{T}{T}lineageTag: {uid('m' + name)}", ""]
    return "\n".join(lines)


def table(name: str, columns: list[str], measures: list[str], m_query: str) -> str:
    parts = [f"table {name}", f"{T}lineageTag: {uid('t' + name)}", ""]
    parts += measures + columns
    parts += [f"{T}partition {name} = m", f"{T}{T}mode: import", f"{T}{T}source =", indent(m_query, 4), ""]
    return "\n".join(parts) + "\n"


PCT, PCT2, INT, DEC1, DEC2 = "0.0%", "0.00%", "#,0", "#,0.0", "#,0.00"

# ---- fact_orders ------------------------------------------------------
fact_types = [
    ("order_id", "type text"), ("customer_id", "type text"), ("customer_state", "type text"),
    ("purchased_at", "type datetime"), ("purchase_date", "type date"), ("purchase_month", "type datetime"),
    ("delivered_at", "type datetime"), ("promised_at", "type datetime"),
    ("delivery_days", "Int64.Type"), ("days_vs_promise", "Int64.Type"), ("is_late", "Int64.Type"),
    ("review_score", "type number"), ("is_negative_review", "Int64.Type"), ("order_value", "type number"),
    ("payment_type", "type text"), ("installments", "Int64.Type"), ("n_items", "Int64.Type"),
    ("n_sellers", "Int64.Type"), ("seller_id", "type text"), ("seller_state", "type text"),
    ("category", "type text"), ("items_price", "type number"), ("freight_value", "type number"), ("route", "type text"),
]
fact_extra = """
WithMonth = Table.AddColumn({prev}, "Month", each Date.From([purchase_month]), type date)
WithYear = Table.AddColumn({prev}, "Year", each Date.Year([purchase_month]), Int64.Type)
WithStatus = Table.AddColumn({prev}, "Delivery Status", each if [is_late] = 1 then "Late" else "On time / early", type text)
WithBucket = Table.AddColumn({prev}, "Delay Bucket", each let d = [days_vs_promise] in if d = null then null else if d <= -10 then "10+ days early" else if d <= -1 then "1-9 days early" else if d = 0 then "On promised day" else if d <= 3 then "1-3 days late" else if d <= 7 then "4-7 days late" else "8+ days late", type text)
WithOrder = Table.AddColumn({prev}, "Delay Order", each let d = [days_vs_promise] in if d = null then null else if d <= -10 then 1 else if d <= -1 then 2 else if d = 0 then 3 else if d <= 3 then 4 else if d <= 7 then 5 else 6, Int64.Type)
"""
fact_cols = [
    col("order_id", "string"), col("customer_id", "string"), col("customer_state", "string"),
    col("purchased_at", "dateTime", "General Date"), col("purchase_date", "dateTime", "Short Date"),
    col("purchase_month", "dateTime", "mmm yyyy", hidden=True),
    col("delivered_at", "dateTime", "General Date"), col("promised_at", "dateTime", "General Date"),
    col("delivery_days", "int64", "0"), col("days_vs_promise", "int64", "0"), col("is_late", "int64", "0"),
    col("review_score", "double", "0.0"), col("is_negative_review", "int64", "0"), col("order_value", "double", DEC2),
    col("payment_type", "string"), col("installments", "int64", "0"), col("n_items", "int64", "0"),
    col("n_sellers", "int64", "0"), col("seller_id", "string"), col("seller_state", "string"),
    col("category", "string"), col("items_price", "double", DEC2), col("freight_value", "double", DEC2),
    col("route", "string"),
    col("Month", "dateTime", "mmm yyyy"), col("Year", "int64", "0"), col("Delivery Status", "string"),
    col("Delay Bucket", "string", sort_by="Delay Order"), col("Delay Order", "int64", "0", hidden=True),
]
F = "fact_orders"
fact_measures = [
    measure("Orders", f"COUNTROWS({F})", INT, "Volume"),
    measure("Revenue", f"SUM({F}[order_value])", INT, "Volume"),
    measure("Avg Order Value", "DIVIDE([Revenue], [Orders])", DEC2, "Volume"),
    measure("Customers", f"DISTINCTCOUNT({F}[customer_id])", INT, "Volume"),
    measure("Sellers", f"DISTINCTCOUNT({F}[seller_id])", INT, "Volume"),
    measure("Late Orders", f"SUM({F}[is_late])", INT, "Delivery"),
    measure("Late Rate", "DIVIDE([Late Orders], [Orders])", PCT, "Delivery"),
    measure("Avg Delivery Days", f"AVERAGE({F}[delivery_days])", DEC1, "Delivery"),
    measure("Avg Days vs Promise", f"AVERAGE({F}[days_vs_promise])", DEC1, "Delivery"),
    measure("Share of Late Orders", f"DIVIDE([Late Orders], CALCULATE([Late Orders], ALL({F})))", PCT, "Delivery"),
    measure("Late vs National", f"DIVIDE([Late Rate], CALCULATE([Late Rate], ALL({F})))", '0.00"x"', "Delivery"),
    measure("Avg Review", f"AVERAGE({F}[review_score])", DEC2, "Satisfaction"),
    measure("Negative Review Rate", f"DIVIDE(SUM({F}[is_negative_review]), COUNT({F}[review_score]))", PCT, "Satisfaction"),
    measure("Freight Share", f"DIVIDE(SUM({F}[freight_value]), SUM({F}[items_price]))", PCT, "Volume"),
]

# ---- dim_customers ----------------------------------------------------
dim_types = [
    ("customer_id", "type text"), ("n_orders", "Int64.Type"), ("n_purchase_days", "Int64.Type"),
    ("lifetime_value", "type number"), ("first_purchase_date", "type date"), ("last_purchase_date", "type date"),
    ("is_repeat", "Int64.Type"), ("repeat_180d", "Int64.Type"), ("first_order_late", "Int64.Type"),
    ("first_order_review", "type number"), ("first_order_category", "type text"), ("customer_state", "type text"),
    ("first_payment_type", "type text"), ("first_order_value", "type number"),
]
dim_extra = """
WithDelivery = Table.AddColumn({prev}, "First Order Delivery", each if [first_order_late] = 1 then "Late" else "On time / early", type text)
WithBand = Table.AddColumn({prev}, "First Rating Band", each let s = [first_order_review] in if s = null then "No review" else if s <= 2 then "1-2 stars" else if s <= 3 then "3 stars" else "4-5 stars", type text)
WithWindow = Table.AddColumn({prev}, "Full 180d Window", each if [first_purchase_date] < #date(2018, 3, 1) then 1 else 0, Int64.Type)
"""
dim_cols = [
    col("customer_id", "string"), col("n_orders", "int64", "0"), col("n_purchase_days", "int64", "0"),
    col("lifetime_value", "double", DEC2), col("first_purchase_date", "dateTime", "Short Date"),
    col("last_purchase_date", "dateTime", "Short Date"), col("is_repeat", "int64", "0"), col("repeat_180d", "int64", "0"),
    col("first_order_late", "int64", "0"), col("first_order_review", "double", "0.0"),
    col("first_order_category", "string"), col("customer_state", "string"), col("first_payment_type", "string"),
    col("first_order_value", "double", DEC2), col("First Order Delivery", "string"), col("First Rating Band", "string"),
    col("Full 180d Window", "int64", "0"),
]
D = "dim_customers"
dim_measures = [
    measure("Customer Count", f"COUNTROWS({D})", INT, "Retention"),
    measure("Repeat Customers", f"SUM({D}[is_repeat])", INT, "Retention"),
    measure("Repeat Rate", "DIVIDE([Repeat Customers], [Customer Count])", PCT2, "Retention"),
    measure("Repeat 180d Rate", f"CALCULATE(AVERAGE({D}[repeat_180d]), {D}[Full 180d Window] = 1)", PCT2, "Retention"),
    measure("Repeat 180d Rate (n>=500)",
            f"IF(CALCULATE(COUNTROWS({D}), {D}[Full 180d Window] = 1) >= 500, [Repeat 180d Rate])", PCT2, "Retention"),
    measure("Avg Lifetime Value", f"AVERAGE({D}[lifetime_value])", DEC2, "Retention"),
    measure("Repeat Revenue Share",
            f"DIVIDE(CALCULATE(SUM({D}[lifetime_value]), {D}[is_repeat] = 1), SUM({D}[lifetime_value]))", PCT, "Retention"),
]

# ---- small summary tables --------------------------------------------
seg_types = [("segment", "type text"), ("customers", "Int64.Type"), ("pct_customers", "type number"),
             ("revenue_brl", "type number"), ("pct_revenue", "type number"), ("avg_value_brl", "type number"),
             ("avg_recency_days", "type number")]
seg_cols = [col("segment", "string"), col("customers", "int64", INT), col("pct_customers", "double", '0.0"%"'),
            col("revenue_brl", "double", INT), col("pct_revenue", "double", '0.0"%"'), col("avg_value_brl", "double", INT),
            col("avg_recency_days", "double", "0")]
gap_types = [("gap_bucket", "type text"), ("customers", "Int64.Type"), ("pct", "type number"), ("cumulative_pct", "type number")]
gap_cols = [col("gap_bucket", "string"), col("customers", "int64", INT), col("pct", "double", '0.0"%"'),
            col("cumulative_pct", "double", '0.0"%"')]
gap_measures = [measure("Share of Repeat Customers", "DIVIDE(SUM(days_to_second_purchase[pct]), 100)", PCT, "Retention")]
coh_types = [("cohort_month", "type date"), ("cohort_size", "Int64.Type")] + [(f"m{i}", "type number") for i in range(1, 7)]
coh_cols = [col("cohort_month", "dateTime", "mmm yyyy"), col("cohort_size", "int64", INT)] + \
           [col(f"m{i}", "double", '0.00"%"') for i in range(1, 7)]

TABLES = {
    F: table(F, fact_cols, fact_measures,
             csv_m("fact_orders.csv", fact_types, fact_extra,
                   rows_filter="[purchase_month] >= #datetime(2017,1,1,0,0,0) and [purchase_month] < #datetime(2018,9,1,0,0,0)")),
    D: table(D, dim_cols, dim_measures, csv_m("dim_customers.csv", dim_types, dim_extra)),
    "customer_segments": table("customer_segments", seg_cols, [], csv_m("customer_segments.csv", seg_types)),
    "days_to_second_purchase": table("days_to_second_purchase", gap_cols, gap_measures,
                                     csv_m("days_to_second_purchase.csv", gap_types)),
    "cohort_retention": table("cohort_retention", coh_cols, [], csv_m("cohort_retention.csv", coh_types)),
}


def write_semantic_model(base: Path) -> None:
    d = base / "definition"
    (d / "tables").mkdir(parents=True, exist_ok=True)
    (base / "definition.pbism").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2", "settings": {}}, indent=2), encoding="utf-8")
    (d / "database.tmdl").write_text(f"database\n{T}compatibilityLevel: 1567\n\n", encoding="utf-8")
    refs = "\n".join(f"ref table {t}" for t in TABLES)
    order = json.dumps(["DataFolder"] + list(TABLES))
    (d / "model.tmdl").write_text(
        f"model Model\n{T}culture: en-US\n{T}defaultPowerBIDataSourceVersion: powerBI_V3\n{T}sourceQueryCulture: en-US\n"
        f"{T}dataAccessOptions\n{T}{T}legacyRedirects\n{T}{T}returnErrorValuesAsNull\n\n"
        f"annotation PBI_QueryOrder = {order}\n\nannotation __PBI_TimeIntelligenceEnabled = 0\n\n{refs}\n\n",
        encoding="utf-8")
    folder = str(DATA).replace("/", "\\").rstrip("\\") + "\\"
    (d / "expressions.tmdl").write_text(
        f'expression DataFolder = "{folder}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
        f"{T}lineageTag: {uid('param-datafolder')}\n\n{T}annotation PBI_ResultType = Text\n\n", encoding="utf-8")
    (d / "relationships.tmdl").write_text(
        f"relationship {uid('rel-fact-dim')}\n{T}fromColumn: {F}.customer_id\n{T}toColumn: {D}.customer_id\n\n",
        encoding="utf-8")
    for name, body in TABLES.items():
        (d / "tables" / f"{name}.tmdl").write_text(body, encoding="utf-8")


# =====================================================================
# 2. REPORT (report.json, PBIR-Legacy format)
# =====================================================================
ALIAS = {F: "f", D: "d", "customer_segments": "s", "days_to_second_purchase": "g", "cohort_retention": "c"}


def lit(v: str) -> dict:
    return {"expr": {"Literal": {"Value": v}}}


def field(entity: str, prop: str, kind: str) -> dict:
    key = "Measure" if kind == "m" else "Column"
    return {key: {"Expression": {"SourceRef": {"Source": ALIAS[entity]}}, "Property": prop}}


def visual(page: str, vtype: str, x, y, w, h, roles: dict, title: str | None = None, order=None, objects=None, z=0):
    """roles: {role: [(entity, prop, 'm'|'c'), ...]}; order: (entity, prop, kind, 'asc'|'desc')."""
    select, projections, entities, seen = [], {}, [], set()
    for role, items in roles.items():
        projections[role] = []
        for i, (ent, prop, kind) in enumerate(items):
            ref = f"{ent}.{prop}"
            p = {"queryRef": ref}
            if role in ("Category", "Rows", "Values") and vtype not in ("tableEx", "card") and i == 0:
                p["active"] = True
            projections[role].append(p)
            if ent not in entities:
                entities.append(ent)
            if ref not in seen:
                seen.add(ref)
                select.append({**field(ent, prop, kind), "Name": ref, "NativeReferenceName": prop})
    query = {"Version": 2, "From": [{"Name": ALIAS[e], "Entity": e, "Type": 0} for e in entities], "Select": select}
    if order:
        ent, prop, kind, direction = order
        if ent not in entities:
            query["From"].append({"Name": ALIAS[ent], "Entity": ent, "Type": 0})
        query["OrderBy"] = [{"Direction": 2 if direction == "desc" else 1, "Expression": field(ent, prop, kind)}]
    name = hexname(page + vtype + str(x) + str(y))
    sv = {"visualType": vtype, "projections": projections, "prototypeQuery": query, "drillFilterOtherVisuals": True}
    if order:
        sv["hasDefaultSort"] = True
    if objects:
        sv["objects"] = objects
    vc = {}
    if title:
        vc["title"] = [{"properties": {"show": lit("true"), "text": lit(f"'{title}'")}}]
    if vc:
        sv["vcObjects"] = vc
    return container(name, x, y, w, h, z, sv)


def container(name, x, y, w, h, z, single_visual) -> dict:
    cfg = {"name": name, "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z}}],
           "singleVisual": single_visual}
    return {"config": json.dumps(cfg), "filters": "[]", "height": h, "width": w, "x": x, "y": y, "z": z}


def textbox(page, x, y, w, h, text, size="20pt", bold=True, z=0, color=None):
    style = {"fontFamily": "Segoe UI Semibold" if bold else "Segoe UI", "fontSize": size}
    if color:
        style["color"] = color
    sv = {"visualType": "textbox", "drillFilterOtherVisuals": True,
          "objects": {"general": [{"properties": {"paragraphs": [{"textRuns": [{"value": text, "textStyle": style}]}]}}]}}
    return container(hexname(page + text), x, y, w, h, z, sv)


def slicer(page, x, y, w, h, ent, prop, z):
    objs = {"data": [{"properties": {"mode": lit("'Dropdown'")}}]}
    return visual(page, "slicer", x, y, w, h, {"Values": [(ent, prop, "c")]}, objects=objs, z=z)


def cards(page, y, measures, z0):
    n, gap, left, width = len(measures), 8, 12, 1256
    w = (width - gap * (n - 1)) / n
    return [visual(page, "card", round(left + i * (w + gap), 1), y, round(w, 1), 88, {"Values": [(e, m, "m")]}, z=z0 + i)
            for i, (e, m) in enumerate(measures)]


def header(page, title, subtitle, slicers):
    out = [textbox(page, 12, 4, 700, 40, title, "20pt", z=0),
           textbox(page, 12, 42, 700, 28, subtitle, "11pt", bold=False, z=1, color="#605E5C")]
    sw, gap = 128, 8
    x0 = 1268 - len(slicers) * sw - (len(slicers) - 1) * gap
    for i, (ent, prop) in enumerate(slicers):
        out.append(slicer(page, x0 + i * (sw + gap), 8, sw, 62, ent, prop, z=10 + i))
    return out


def page_overview():
    p = "overview"
    v = header(p, "Olist marketplace · Executive overview",
               "96K delivered orders, Jan 2017 – Aug 2018 · every slicer and click filters the whole page",
               [(F, "Year"), (F, "customer_state"), (F, "category"), (F, "payment_type")])
    v += cards(p, 78, [(F, "Orders"), (F, "Revenue"), (F, "Avg Order Value"), (F, "Late Rate"), (F, "Avg Review"),
                       (F, "Negative Review Rate")], 20)
    v.append(visual(p, "lineChart", 12, 174, 624, 262, {"Category": [(F, "Month", "c")], "Y": [(F, "Late Rate", "m")]},
                    "Late-delivery rate by month: spikes in Nov 2017 and Feb–Mar 2018", (F, "Month", "c", "asc"), z=30))
    v.append(visual(p, "clusteredColumnChart", 644, 174, 624, 262, {"Category": [(F, "Month", "c")], "Y": [(F, "Orders", "m")]},
                    "Orders by month", (F, "Month", "c", "asc"), z=31))
    v.append(visual(p, "clusteredColumnChart", 12, 444, 410, 268,
                    {"Category": [(F, "Delay Bucket", "c")], "Y": [(F, "Avg Review", "m")]},
                    "Every day late costs stars: avg review by delivery vs promise", (F, "Delay Bucket", "c", "asc"), z=32))
    v.append(visual(p, "clusteredBarChart", 430, 444, 410, 268,
                    {"Category": [(F, "customer_state", "c")], "Y": [(F, "Late Rate", "m")]},
                    "Late rate by customer state", (F, "Late Rate", "m", "desc"), z=33))
    v.append(visual(p, "clusteredBarChart", 848, 444, 420, 268,
                    {"Category": [(F, "category", "c")], "Y": [(F, "Revenue", "m")]},
                    "Revenue by product category", (F, "Revenue", "m", "desc"), z=34))
    return p, "Executive Overview", v


def page_delivery():
    p = "delivery"
    v = header(p, "Delivery & sellers: where lateness comes from",
               "Late = delivered after the date promised at checkout · tables sorted by late orders",
               [(F, "Year"), (F, "customer_state"), (F, "seller_state"), (F, "category")])
    v += cards(p, 78, [(F, "Late Orders"), (F, "Late Rate"), (F, "Share of Late Orders"), (F, "Avg Delivery Days"),
                       (F, "Avg Days vs Promise"), (F, "Sellers")], 20)
    v.append(visual(p, "tableEx", 12, 174, 624, 262,
                    {"Values": [(F, "route", "c"), (F, "Orders", "m"), (F, "Late Orders", "m"), (F, "Late Rate", "m"),
                                (F, "Late vs National", "m"), (F, "Avg Delivery Days", "m"), (F, "Avg Review", "m")]},
                    "Delivery lanes (seller state -> customer state)", (F, "Late Orders", "m", "desc"), z=30))
    v.append(visual(p, "clusteredColumnChart", 644, 174, 624, 262, {"Category": [(F, "Month", "c")], "Y": [(F, "Late Orders", "m")]},
                    "Late orders by month: 3 peak months carry 46% of them", (F, "Month", "c", "asc"), z=31))
    v.append(visual(p, "tableEx", 12, 444, 624, 268,
                    {"Values": [(F, "seller_id", "c"), (F, "seller_state", "c"), (F, "Orders", "m"), (F, "Late Orders", "m"),
                                (F, "Late Rate", "m"), (F, "Share of Late Orders", "m"), (F, "Avg Review", "m")]},
                    "Sellers ranked by late orders (102 sellers = 50% of all late)", (F, "Late Orders", "m", "desc"), z=32))
    v.append(visual(p, "clusteredColumnChart", 644, 444, 306, 268,
                    {"Category": [(F, "Delay Bucket", "c")], "Y": [(F, "Negative Review Rate", "m")]},
                    "% of 1-2 star reviews by delay", (F, "Delay Bucket", "c", "asc"), z=33))
    v.append(visual(p, "clusteredBarChart", 958, 444, 310, 268,
                    {"Category": [(F, "seller_state", "c")], "Y": [(F, "Share of Late Orders", "m")]},
                    "Share of late orders by seller state", (F, "Share of Late Orders", "m", "desc"), z=34))
    return p, "Delivery & Sellers", v


def page_customers():
    p = "customers"
    v = header(p, "Customers & retention: who comes back",
               "Repeat = bought on 2+ different days · 180-day rate counts only customers with a full window",
               [(D, "customer_state"), (D, "first_order_category"), (D, "First Order Delivery")])
    v += cards(p, 78, [(D, "Customer Count"), (D, "Repeat Customers"), (D, "Repeat Rate"), (D, "Repeat 180d Rate"),
                       (D, "Avg Lifetime Value"), (D, "Repeat Revenue Share")], 20)
    v.append(visual(p, "clusteredColumnChart", 12, 174, 300, 262,
                    {"Category": [(D, "First Order Delivery", "c")], "Y": [(D, "Repeat 180d Rate", "m")]},
                    "Repeat rate: late vs on-time first order", None, z=30))
    v.append(visual(p, "clusteredColumnChart", 320, 174, 300, 262,
                    {"Category": [(D, "First Rating Band", "c")], "Y": [(D, "Repeat 180d Rate", "m")]},
                    "Repeat rate by first-order rating", (D, "First Rating Band", "c", "asc"), z=31))
    v.append(visual(p, "clusteredBarChart", 628, 174, 640, 262,
                    {"Category": [(D, "first_order_category", "c")], "Y": [(D, "Repeat 180d Rate (n>=500)", "m")]},
                    "First purchase category predicts loyalty (categories with 500+ customers)",
                    (D, "Repeat 180d Rate (n>=500)", "m", "desc"), z=32))
    v.append(visual(p, "clusteredColumnChart", 12, 444, 360, 268,
                    {"Category": [("days_to_second_purchase", "gap_bucket", "c")],
                     "Y": [("days_to_second_purchase", "Share of Repeat Customers", "m")]},
                    "Days to second purchase: 76% within 6 months", ("days_to_second_purchase", "gap_bucket", "c", "asc"), z=33))
    v.append(visual(p, "tableEx", 380, 444, 470, 268,
                    {"Values": [("customer_segments", "segment", "c"), ("customer_segments", "customers", "c"),
                                ("customer_segments", "pct_customers", "c"), ("customer_segments", "pct_revenue", "c"),
                                ("customer_segments", "avg_value_brl", "c"), ("customer_segments", "avg_recency_days", "c")]},
                    "Customer segments: who to target", ("customer_segments", "segment", "c", "asc"), z=34))
    v.append(visual(p, "tableEx", 858, 444, 410, 268,
                    {"Values": [("cohort_retention", "cohort_month", "c"), ("cohort_retention", "cohort_size", "c")] +
                               [("cohort_retention", f"m{i}", "c") for i in range(1, 7)]},
                    "Monthly cohorts: % buying again in month 1-6", ("cohort_retention", "cohort_month", "c", "asc"), z=35))
    return p, "Customers & Retention", v


def write_report(base: Path) -> None:
    theme_dir = base / "StaticResources" / "SharedResources" / "BaseThemes"
    theme_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(THEME_SRC, theme_dir / "CY25SU12.json")
    (base / "definition.pbir").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": "../Olist.SemanticModel"}}}, indent=2), encoding="utf-8")
    config = {
        "version": "5.69",
        "themeCollection": {"baseTheme": {"name": "CY25SU12", "type": 2,
                                          "version": {"visual": "2.5.0", "report": "3.1.0", "page": "2.3.0"}}},
        "activeSectionIndex": 0, "defaultDrillFilterOtherVisuals": True, "linguisticSchemaSyncVersion": 0,
        "settings": {"useNewFilterPaneExperience": True, "allowChangeFilterTypes": True,
                     "useStylableVisualContainerHeader": True, "queryLimitOption": 6, "useEnhancedTooltips": True,
                     "exportDataMode": 1, "useDefaultAggregateDisplayName": True},
        "objects": {"section": [{"properties": {"verticalAlignment": lit("'Top'")}}]},
    }
    sections = []
    for i, (name, display, visuals) in enumerate([page_overview(), page_delivery(), page_customers()]):
        sections.append({"config": "{}", "displayName": display, "displayOption": 1, "filters": "[]",
                         "height": 720.0, "name": hexname("section" + name), "ordinal": i,
                         "visualContainers": visuals, "width": 1280.0})
    report = {"config": json.dumps(config), "layoutOptimization": 0,
              "resourcePackages": [{"resourcePackage": {"disabled": False, "items": [
                  {"name": "CY25SU12", "path": "BaseThemes/CY25SU12.json", "type": 202}],
                  "name": "SharedResources", "type": 2}}],
              "sections": sections}
    (base / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def main() -> None:
    if OUT.exists():
        for sub in ("Olist.Report", "Olist.SemanticModel"):
            # keep Power BI's local cache/settings folder (.pbi) out of the way of a clean rebuild
            target = OUT / sub
            for p in [target / "report.json", target / "definition"]:
                if p.is_dir():
                    shutil.rmtree(p)
                elif p.exists():
                    p.unlink()
    OUT.mkdir(exist_ok=True)
    write_semantic_model(OUT / "Olist.SemanticModel")
    write_report(OUT / "Olist.Report")
    (OUT / "Olist.pbip").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": "Olist.Report"}}],
        "settings": {"enableAutoRecovery": True}}, indent=2), encoding="utf-8")
    sections = json.loads((OUT / "Olist.Report" / "report.json").read_text(encoding="utf-8"))["sections"]
    n = sum(len(s["visualContainers"]) for s in sections)
    print(f"written {OUT}: {len(TABLES)} tables, {n} visuals on {len(sections)} pages")


if __name__ == "__main__":
    main()
