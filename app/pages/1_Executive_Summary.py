"""Tab 1 — Executive Summary."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st
import plotly.express as px

from app._shared import page_setup, year_picker, fmt_int, fmt_pct
from core import queries as Q

page_setup("Executive Summary", "📈")

year = year_picker("Reporting year")
if year is None:
    st.stop()

total = Q.total_ytd(year)
yoy = Q.yoy_growth(year)

top_states = Q.top_n("State", "MonthWise", n=1, years=[year])
top_makers = Q.top_n("Maker", "MonthWise", n=1, years=[year])
fuel_mix = Q.market_share("Fuel", "MonthWise", n=12, years=[year])
ev_keys = [k for k in fuel_mix.index
           if any(t in k.upper() for t in ("ELECTRIC", "EV", "HYBRID"))]
ev_pct = fuel_mix.loc[ev_keys, "share_pct"].sum() if ev_keys else 0.0
top_state_name = top_states.index[0] if not top_states.empty else "—"
top_maker_name = top_makers.index[0] if not top_makers.empty else "—"

# Numeric KPIs (these get the big metric treatment)
c1, c2, c3 = st.columns(3)
c1.metric(f"Total registrations · {year}", fmt_int(total))
c2.metric("YoY growth", fmt_pct(yoy))
c3.metric("EV / hybrid share", f"{ev_pct:.2f}%")

# Text KPIs (names can be long → render as markdown so they don't get truncated)
t1, t2 = st.columns(2)
with t1:
    st.markdown(
        f"<div style='font-size:0.85rem;opacity:0.7'>Top state</div>"
        f"<div style='font-size:1.6rem;font-weight:600;line-height:1.2'>{top_state_name}</div>",
        unsafe_allow_html=True,
    )
with t2:
    st.markdown(
        f"<div style='font-size:0.85rem;opacity:0.7'>Top maker</div>"
        f"<div style='font-size:1.6rem;font-weight:600;line-height:1.2'>{top_maker_name}</div>",
        unsafe_allow_html=True,
    )

st.divider()

# Monthly trend, current vs previous year ------------------------------------
left, right = st.columns([2, 1])

with left:
    st.subheader("Monthly registrations")
    cur = Q.monthly_trend(year)
    cur["year"] = str(year)
    frames = [cur]
    if Q.total_ytd(year - 1) > 0:
        prev = Q.monthly_trend(year - 1)
        prev["year"] = str(year - 1)
        frames.append(prev)
    import pandas as pd
    df = pd.concat(frames, ignore_index=True)
    fig = px.line(df, x="month", y="value", color="year", markers=True,
                  labels={"value": "Registrations", "month": "Month"})
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Fuel mix")
    pie_df = fuel_mix.reset_index().rename(columns={"index": "fuel"})
    pie_df.columns = ["fuel", "value", "share_pct"]
    fig = px.pie(pie_df, names="fuel", values="value", hole=0.5)
    fig.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig, use_container_width=True)

st.divider()

st.subheader("Top performers")
t1, t2 = st.columns(2)
with t1:
    st.markdown("**Top 10 states**")
    st.dataframe(Q.top_n("State", "MonthWise", n=10, years=[year])[["TOTAL"]]
                 .style.format("{:,.0f}"), use_container_width=True)
with t2:
    st.markdown("**Top 10 makers**")
    st.dataframe(Q.top_n("Maker", "MonthWise", n=10, years=[year])[["TOTAL"]]
                 .style.format("{:,.0f}"), use_container_width=True)
