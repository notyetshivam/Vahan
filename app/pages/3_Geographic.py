"""Tab 3 — Geographic (state-wise) trends."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st
import plotly.express as px

from app._shared import page_setup, year_picker
from core import queries as Q

page_setup("Geographic Trends", "🗺️")

year = year_picker("Year")
if year is None:
    st.stop()

leaderboard = Q.top_n("State", "MonthWise", n=40, years=[year])

st.subheader("State leaderboard")
lb = leaderboard.reset_index()
fig = px.bar(
    lb, x="TOTAL", y="row_value", orientation="h",
    color="TOTAL", color_continuous_scale="Turbo",
    labels={"row_value": "State", "TOTAL": "Registrations"},
)
fig.update_layout(
    yaxis={"categoryorder": "total ascending"},
    height=900, coloraxis_showscale=False,
)
st.plotly_chart(fig, use_container_width=True)

st.divider()

states = Q.list_dim_values("State")
sel = st.selectbox("Drill into a state", states,
                   index=states.index("MAHARASHTRA") if "MAHARASHTRA" in states else 0)
st.subheader(f"{sel} — monthly trajectory")
trend = Q.monthly_trend(year, row_value=sel)
fig = px.area(trend, x="month", y="value", markers=True,
              labels={"value": "Registrations", "month": "Month"})
st.plotly_chart(fig, use_container_width=True)

c1, c2 = st.columns(2)
with c1:
    st.markdown(f"**{sel} — vehicle category mix**")
    cat = Q.slice_fact("State", "VehicleCategory", row_values=[sel], years=[year])
    if not cat.empty:
        fig = px.bar(cat.sort_values("value", ascending=True),
                     x="value", y="col_value", orientation="h",
                     labels={"value": "Registrations", "col_value": "Category"})
        st.plotly_chart(fig, use_container_width=True)
with c2:
    st.markdown(f"**{sel} — vehicle class breakdown (top 15)**")
    cls = Q.slice_fact("State", "VehicleClass", row_values=[sel], years=[year])
    if not cls.empty:
        top = cls.groupby("col_value", observed=True)["value"].sum().nlargest(15).reset_index()
        fig = px.bar(top.sort_values("value", ascending=True),
                     x="value", y="col_value", orientation="h",
                     labels={"value": "Registrations", "col_value": "Vehicle class"})
        st.plotly_chart(fig, use_container_width=True)
