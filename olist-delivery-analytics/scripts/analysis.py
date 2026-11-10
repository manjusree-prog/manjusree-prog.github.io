"""Statistical checks, charts, dashboard data and Power BI exports.

Reads data/olist.db (built by load_to_sqlite.py) and the CSVs from run_sql.py.

Usage (from the repository root):
    python scripts/analysis.py
"""
import json
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "olist.db"
RES = ROOT / "outputs" / "sql_results"
FIG = ROOT / "outputs" / "figures"
PBI = ROOT / "powerbi" / "model"
DASH = ROOT / "docs"
for d in (FIG, PBI, DASH):
    d.mkdir(parents=True, exist_ok=True)

BLUE, RED, GREY = "#1F5FA8", "#C8423B", "#8A8F98"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titleweight": "bold", "axes.titlesize": 11})

con = sqlite3.connect(DB)
f = pd.read_sql_query(
    "SELECT * FROM fact_delivered WHERE purchase_month BETWEEN '2017-01' AND '2018-08'", con)
res = {n.stem: pd.read_csv(n) for n in RES.glob("*.csv")}

# ---------------------------------------------------------------- statistics
late, ontime = f[f.is_late == 1], f[f.is_late == 0]
rv_late, rv_on = late.review_score.dropna(), ontime.review_score.dropna()
mw = stats.mannwhitneyu(rv_late, rv_on, alternative="less")
neg_late = (rv_late <= 2).mean()
neg_on = (rv_on <= 2).mean()

rep = res["repeat_customers"].set_index("first_delivery")
n1, p1 = rep.loc["first order on time", ["customers", "repeat_purchase_pct"]]
n2, p2 = rep.loc["first order late", ["customers", "repeat_purchase_pct"]]
p1, p2 = p1 / 100, p2 / 100
pp = (p1 * n1 + p2 * n2) / (n1 + n2)
z = (p1 - p2) / np.sqrt(pp * (1 - pp) * (1 / n1 + 1 / n2))
p_rep = 2 * (1 - stats.norm.cdf(abs(z)))

sel = res["seller_late_concentration"]
top10 = sel[sel.pct_of_sellers <= 10]
top10_share_late = top10.cum_pct_of_late_orders.max()
top10_share_orders = 100 * top10.orders.sum() / sel.orders.sum()
sellers_with_late = 100 * (sel.late_orders > 0).mean()
# watch-list: sellers with real volume and a late rate far above average
watch = sel[(sel.orders >= 30) & (sel.seller_late_rate_pct >= 15)]
watch.to_csv(ROOT / "outputs" / "seller_watchlist.csv", index=False)

state = res["late_rate_by_state"].copy()
state["late_orders"] = (state.orders * state.late_rate_pct / 100).round().astype(int)

# rough impact: negative reviews avoided if late orders behaved like on-time ones
extra_negative = int(round(len(rv_late) * (neg_late - neg_on)))

summary = {
    "late_orders": int(len(late)),
    "late_rate_pct": round(100 * f.is_late.mean(), 1),
    "avg_review_late": round(rv_late.mean(), 2),
    "avg_review_ontime": round(rv_on.mean(), 2),
    "negative_review_pct_late": round(100 * neg_late, 1),
    "negative_review_pct_ontime": round(100 * neg_on, 1),
    "mann_whitney_p": float(mw.pvalue),
    "extra_negative_reviews_from_lateness": extra_negative,
    "repeat_pct_ontime": round(100 * p1, 2),
    "repeat_pct_late": round(100 * p2, 2),
    "repeat_z": round(float(z), 2),
    "repeat_p": round(float(p_rep), 4),
    "top10pct_sellers_share_of_late_orders": round(top10_share_late, 1),
    "top10pct_sellers_share_of_orders": round(top10_share_orders, 1),
    "pct_sellers_with_any_late_order": round(sellers_with_late, 1),
    "watchlist_sellers": int(len(watch)),
    "watchlist_pct_of_sellers": round(100 * len(watch) / len(sel), 1),
    "watchlist_share_of_late_orders": round(100 * watch.late_orders.sum() / sel.late_orders.sum(), 1),
    "watchlist_share_of_orders": round(100 * watch.orders.sum() / sel.orders.sum(), 1),
    "watchlist_late_rate": round(100 * watch.late_orders.sum() / watch.orders.sum(), 1),
}
(ROOT / "outputs" / "key_numbers.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))

# ---------------------------------------------------------------- charts
m = res["monthly_trend"]
fig, ax = plt.subplots(figsize=(9, 3.6))
ax.bar(m.purchase_month, m.orders, color="#D6E2F0", label="Delivered orders")
ax.set_ylabel("Orders")
ax2 = ax.twinx()
ax2.plot(m.purchase_month, m.late_rate_pct, color=RED, marker="o", lw=2, label="Late rate %")
ax2.set_ylabel("Late deliveries (%)")
ax2.spines["top"].set_visible(False)
for lbl in ("2017-11", "2018-03"):
    i = m.index[m.purchase_month == lbl][0]
    ax2.annotate(f"{m.late_rate_pct[i]}%", (i, m.late_rate_pct[i]), textcoords="offset points",
                 xytext=(0, 7), ha="center", color=RED, fontweight="bold")
ax.set_xticks(range(len(m)))
ax.set_xticklabels([x[2:] for x in m.purchase_month], rotation=45, fontsize=8)
ax.set_title("Late deliveries spike in Nov 2017 and Feb-Mar 2018")
fig.tight_layout(); fig.savefig(FIG / "01_monthly_late_rate.png", dpi=150); plt.close(fig)

r = res["review_by_delivery_outcome"]
labels = [x.split(". ", 1)[1] for x in r.delivery_outcome]
colors = [BLUE] * 3 + [RED] * 3
fig, ax = plt.subplots(figsize=(8, 3.6))
bars = ax.bar(labels, r.negative_review_pct, color=colors)
ax.bar_label(bars, fmt="%.0f%%", padding=2)
ax.set_ylabel("1-2 star reviews (%)")
ax.set_title("Share of 1-2 star reviews by delivery outcome")
plt.xticks(rotation=15, fontsize=9)
fig.tight_layout(); fig.savefig(FIG / "02_reviews_by_delivery.png", dpi=150); plt.close(fig)

d = res["delivery_stage_breakdown"].set_index("outcome").loc[["on time / early", "late"]]
fig, ax = plt.subplots(figsize=(8, 2.6))
left = np.zeros(2)
for col, c, name in [("approval_days", GREY, "Approval"), ("seller_handling_days", "#E3A33B", "Seller handling"),
                     ("carrier_transit_days", BLUE, "Carrier transit")]:
    ax.barh(["On time / early", "Late"], d[col], left=left, color=c, label=name)
    for i, v in enumerate(d[col]):
        if v > 1.5:
            ax.text(left[i] + v / 2, i, f"{v:.1f}", ha="center", va="center", color="white", fontweight="bold")
    left += d[col].values
ax.axvline(d.promised_days.mean(), color=RED, ls="--", lw=1.5)
ax.text(d.promised_days.mean() + 0.4, 0.5, "avg promised: %.0f days" % d.promised_days.mean(), color=RED, fontsize=9)
ax.set_xlabel("Average days")
ax.set_title("Late orders lose most time in carrier transit")
ax.legend(loc="lower right", fontsize=8, frameon=False)
fig.tight_layout(); fig.savefig(FIG / "03_delivery_stages.png", dpi=150); plt.close(fig)

s = state.sort_values("late_rate_pct")
fig, ax = plt.subplots(figsize=(7, 4.6))
bars = ax.barh(s.customer_state, s.late_rate_pct,
               color=[RED if v >= 10 else BLUE for v in s.late_rate_pct])
ax.bar_label(bars, labels=[f"{v}%  ({n:,} orders)" for v, n in zip(s.late_rate_pct, s.orders)],
             padding=3, fontsize=8)
ax.set_xlabel("Late deliveries (%)")
ax.set_xlim(0, s.late_rate_pct.max() * 1.45)
ax.set_title("Late rate by customer state (states with 500+ orders)")
fig.tight_layout(); fig.savefig(FIG / "04_late_rate_by_state.png", dpi=150); plt.close(fig)

fig, ax = plt.subplots(figsize=(6, 3.6))
ax.plot(sel.pct_of_sellers, sel.cum_pct_of_late_orders, color=BLUE, lw=2)
ax.axvline(10, color=GREY, ls=":")
ax.annotate(f"Top 10% of sellers: {top10_share_late:.0f}% of late orders,\n"
            f"but also {top10_share_orders:.0f}% of all orders", (10, top10_share_late),
            xytext=(20, top10_share_late - 28), arrowprops=dict(arrowstyle="->", color=GREY), fontsize=9)
ax.set_xlabel("% of sellers (ranked by late orders)")
ax.set_ylabel("Cumulative % of late orders")
ax.set_title("Late orders mostly follow seller volume")
ax.set_xlim(0, 60)
fig.tight_layout(); fig.savefig(FIG / "05_seller_concentration.png", dpi=150); plt.close(fig)

# ---------------------------------------------------------------- dashboard data
k = res["kpi_overview"].iloc[0].to_dict()
dash = {
    "kpi": {key: (float(v) if isinstance(v, (np.floating, float)) else int(v)) for key, v in k.items()},
    "summary": summary,
    "monthly": m.to_dict(orient="list"),
    "reviews": {"labels": labels, **r.drop(columns="delivery_outcome").to_dict(orient="list")},
    "stages": res["delivery_stage_breakdown"].to_dict(orient="list"),
    "states": state.to_dict(orient="list"),
    "categories": res["category_performance"].to_dict(orient="list"),
    "sellers": sel[sel.pct_of_sellers <= 60][["pct_of_sellers", "cum_pct_of_late_orders"]]
               .iloc[::5].to_dict(orient="list"),
    "dq": res["dq_summary"].to_dict(orient="list"),
    "pipeline": res["dq_pipeline_counts"].iloc[0].astype(int).to_dict(),
}
(DASH / "dashboard_data.json").write_text(json.dumps(dash, default=lambda o: o.item()))

# ---------------------------------------------------------------- Power BI star schema
fact = pd.read_sql_query("SELECT * FROM fact_delivered", con)
fact.to_csv(PBI / "fact_orders.csv", index=False)
pd.read_sql_query("""
    SELECT DISTINCT f.order_id, i.seller_id, s.seller_state,
           COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
           i.price, i.freight_value
    FROM fact_delivered f
    JOIN order_items i ON i.order_id = f.order_id
    JOIN sellers s ON s.seller_id = i.seller_id
    LEFT JOIN products p ON p.product_id = i.product_id
    LEFT JOIN category_translation t ON t.product_category_name = p.product_category_name
""", con).to_csv(PBI / "fact_order_items.csv", index=False)
dates = pd.DataFrame({"date": pd.date_range(fact.purchase_date.min(), fact.purchase_date.max())})
dates["year"], dates["month"] = dates.date.dt.year, dates.date.dt.month
dates["year_month"] = dates.date.dt.strftime("%Y-%m")
dates["weekday"] = dates.date.dt.day_name()
dates.to_csv(PBI / "dim_date.csv", index=False)
pd.read_csv(ROOT / "data" / "raw" / "olist_customers_dataset.csv")[["customer_state"]] \
    .drop_duplicates().sort_values("customer_state").to_csv(PBI / "dim_state.csv", index=False)
print("charts, dashboard data and Power BI model written")
