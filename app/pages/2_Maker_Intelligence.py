"""Tab 2 — Maker & Brand Intelligence."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st
import plotly.express as px

from app._shared import page_setup, year_picker, fmt_int
from core import queries as Q

page_setup("Maker & Brand Intelligence", "🏭")

year = year_picker("Year")
if year is None:
    st.stop()

all_makers = Q.list_dim_values("Maker")
default_pick = [m for m in ("MARUTI SUZUKI INDIA LTD", "HYUNDAI MOTOR INDIA LTD",
                            "TATA MOTORS LTD", "MAHINDRA & MAHINDRA LIMITED")
                if m in all_makers][:3] or all_makers[:3]

st.caption(f"{len(all_makers):,} makers in dataset. Use the search box to narrow the dropdown.")
sc, mc = st.columns([1, 3])
with sc:
    search = st.text_input("🔎 Search makers", placeholder="e.g. tata, bajaj, hero")
with mc:
    if search:
        s = search.upper().strip()
        filtered = [m for m in all_makers if s in m.upper()]
        st.caption(f"{len(filtered)} match(es) for **{search}**")
    else:
        filtered = all_makers
    # Keep any already-picked makers visible even if they don't match the current search.
    options = list(dict.fromkeys(default_pick + filtered))
    picked = st.multiselect("Pick makers to compare", options, default=default_pick)

if not picked:
    st.info("Select at least one maker above.")
    st.stop()

# Monthly comparison ---------------------------------------------------------
st.subheader("Monthly registrations")
df = Q.slice_fact("Maker", "MonthWise", row_values=picked, years=[year])
if df.empty:
    st.warning("No data for that selection.")
else:
    fig = px.line(df, x="col_value", y="value", color="row_value", markers=True,
                  labels={"col_value": "Month", "value": "Registrations", "row_value": "Maker"})
    st.plotly_chart(fig, use_container_width=True)

# Market share donut ---------------------------------------------------------
left, right = st.columns(2)
with left:
    st.subheader("Top-10 market share (year)")
    share = Q.market_share("Maker", "MonthWise", n=10, years=[year])
    pdf = share.reset_index().rename(columns={"index": "maker"})
    pdf.columns = ["maker", "value", "share_pct"]
    fig = px.pie(pdf, names="maker", values="value", hole=0.45)
    fig.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Category mix for selected makers")
    cat = Q.slice_fact("Maker", "VehicleCategory", row_values=picked, years=[year])
    if cat.empty:
        st.info("No category breakdown available.")
    else:
        fig = px.bar(cat, x="row_value", y="value", color="col_value", barmode="stack",
                     labels={"row_value": "Maker", "value": "Registrations", "col_value": "Category"})
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# YoY for first picked maker -------------------------------------------------
first = picked[0]
st.subheader(f"YoY trajectory — {first}")
prev = year - 1
this = Q.slice_fact("Maker", "MonthWise", row_values=[first], years=[year])
last = Q.slice_fact("Maker", "MonthWise", row_values=[first], years=[prev])
this_total = this["value"].sum() if not this.empty else 0
last_total = last["value"].sum() if not last.empty else 0
delta = ((this_total - last_total) / last_total * 100) if last_total else None
c1, c2, c3 = st.columns(3)
c1.metric(f"{year} YTD", fmt_int(this_total))
c2.metric(f"{prev} YTD", fmt_int(last_total))
c3.metric("Δ %", f"{delta:+.2f}%" if delta is not None else "—")
