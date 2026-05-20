"""Tab 5 — Vehicle Class & Category Deep-Dive."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st
import plotly.express as px

from app._shared import page_setup, year_picker
from core import queries as Q
from core.config import ROW_DIMS, COL_DIMS, DIM_LABELS

page_setup("Vehicle Class & Category Deep-Dive", "🚛")

year = year_picker("Year")
if year is None:
    st.stop()

st.markdown("Pivot any two dimensions against each other.")

c1, c2 = st.columns(2)
with c1:
    row_dim = st.selectbox("Rows", ROW_DIMS,
                           format_func=lambda x: DIM_LABELS.get(x, x),
                           index=ROW_DIMS.index("VehicleClass"))
with c2:
    options = [d for d in COL_DIMS if d != row_dim]
    col_dim = st.selectbox("Columns", options,
                           format_func=lambda x: DIM_LABELS.get(x, x),
                           index=options.index("MonthWise") if "MonthWise" in options else 0)

try:
    df = Q.pivot(row_dim, col_dim, years=[year])
except Exception as e:  # noqa: BLE001
    st.error(f"Could not build pivot: {e}")
    st.stop()

if df.empty:
    st.warning(f"No file for {row_dim} × {col_dim}.")
    st.stop()

n = st.slider("Show top-N rows", 5, min(100, len(df)), 20)
view = df.head(n)
st.dataframe(view.style.format("{:,.0f}"), use_container_width=True)

melt = view.drop(columns=["TOTAL"], errors="ignore").reset_index().melt(
    id_vars="row_value", var_name="col_value", value_name="value")
fig = px.bar(melt, x="row_value", y="value", color="col_value", barmode="stack",
             labels={"row_value": DIM_LABELS.get(row_dim, row_dim),
                     "col_value": DIM_LABELS.get(col_dim, col_dim),
                     "value": "Registrations"})
fig.update_layout(xaxis_tickangle=-30, height=500)
st.plotly_chart(fig, use_container_width=True)
