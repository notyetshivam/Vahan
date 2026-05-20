"""Tab 4 — Fuel & Emissions (the green dashboard)."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st
import plotly.express as px

from app._shared import page_setup, year_picker
from core import queries as Q

page_setup("Fuel & Emissions", "⚡")

year = year_picker("Year")
if year is None:
    st.stop()

fuel_year = Q.market_share("Fuel", "MonthWise", n=20, years=[year])
norms_year = Q.market_share("Norms", "MonthWise", n=20, years=[year])

c1, c2 = st.columns(2)
with c1:
    st.subheader("Fuel mix")
    df = fuel_year.reset_index()
    df.columns = ["fuel", "value", "share_pct"]
    fig = px.pie(df, names="fuel", values="value", hole=0.45)
    fig.update_traces(textinfo="percent+label", textposition="inside")
    st.plotly_chart(fig, use_container_width=True)
with c2:
    st.subheader("Emission-norm mix")
    df = norms_year.reset_index()
    df.columns = ["norm", "value", "share_pct"]
    fig = px.pie(df, names="norm", values="value", hole=0.45)
    fig.update_traces(textinfo="percent+label", textposition="inside")
    st.plotly_chart(fig, use_container_width=True)

st.divider()

st.subheader("Fuel adoption by month")
fm = Q.slice_fact("Fuel", "MonthWise", years=[year])
if not fm.empty:
    fig = px.area(fm, x="col_value", y="value", color="row_value", groupnorm="fraction",
                  labels={"col_value": "Month", "value": "Share", "row_value": "Fuel"})
    fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(fig, use_container_width=True)

st.divider()

st.subheader("Maker-wise EV / Hybrid leaders")
fuel_x_maker = Q.slice_fact("Maker", "VehicleCategory", years=[year])  # placeholder if no maker×fuel file
# Try the real source: there is no Maker×Fuel unified file in the supplied set, so we
# approximate "EV leaders" by intersecting Maker×VehicleClass for known EV classes.
ev_classes = ["e-Rickshaw with Cart (G)", "e-Rickshaw(P)"]
ev = Q.slice_fact("Maker", "VehicleClass", col_values=ev_classes, years=[year])
if ev.empty:
    st.info("No maker-level EV breakdown available in current files. "
            "Add a Maker×Fuel unified file when available.")
else:
    top = ev.groupby("row_value", observed=True)["value"].sum().nlargest(15).reset_index()
    fig = px.bar(top.sort_values("value"), x="value", y="row_value", orientation="h",
                 labels={"value": "EV-class registrations", "row_value": "Maker"})
    st.plotly_chart(fig, use_container_width=True)
