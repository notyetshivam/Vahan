"""Tab 7 — RTO Intelligence (Phase v2).

Cascading Region → State → Tier filters drive every chart on the page.
Each panel renders the Dual View mandated by the PRD addendum:
    [ Plotly chart ]  +  [ sortable / searchable / CSV-downloadable table ]
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st
import plotly.express as px

from app._shared import page_setup, year_picker, dual_view, cascading_rto_filters
from core import queries as Q
from core.config import COL_DIMS, DIM_LABELS, EXPECTED_TOTAL_RTOS

page_setup("RTO Intelligence", "📍")

# ----- Top-of-page health banner --------------------------------------------
dim = Q.dim_rto_df()
if dim.empty:
    st.error("`dim_rto` is empty. Re-run ingest (sidebar of home page).")
    st.stop()
got = len(dim)
if got != EXPECTED_TOTAL_RTOS:
    st.warning(f"dim_rto has {got:,} rows — expected {EXPECTED_TOTAL_RTOS:,}. "
               f"Tier counts may have drifted.")

a, b, c, d = st.columns(4)
counts = dim["urban_rural_proxy"].value_counts(dropna=True).to_dict()
a.metric("RTOs in matrix", f"{got:,}")
b.metric("Urban Tier 1", f"{int(counts.get('Urban - Tier 1', 0)):,}")
c.metric("Urban Tier 2", f"{int(counts.get('Urban - Tier 2', 0)):,}")
d.metric("Rural / Semi-Urban", f"{int(counts.get('Rural / Semi-Urban', 0)):,}")

# ----- Filters --------------------------------------------------------------
year = year_picker("Year")
if year is None:
    st.stop()

filters = cascading_rto_filters()
col_dim = st.sidebar.selectbox(
    "Slice dimension", COL_DIMS,
    format_func=lambda x: DIM_LABELS.get(x, x),
    index=COL_DIMS.index("MonthWise"),
)

st.markdown(
    "**Active filters:** "
    + ", ".join([
        f"Region={filters['regions'] or '∀'}",
        f"State={filters['states'] or '∀'}",
        f"Tier={filters['tiers'] or '∀'}",
        f"Year={year}",
        f"Slice={col_dim}",
    ])
)

q_kwargs = dict(regions=filters["regions"], states=filters["states"],
                tiers=filters["tiers"], years=[year])

# ----- Panel 1: Top-10 RTO Leaderboard --------------------------------------
top_df = Q.rto_top(10, col_dim=col_dim, **q_kwargs)
if top_df.empty:
    st.warning("No data for the current filter combination.")
else:
    fig = px.bar(
        top_df.sort_values("total"),
        x="total", y="rto", orientation="h",
        color="tier", hover_data=["state_name", "region"],
        labels={"total": "Registrations", "rto": "RTO"},
        color_discrete_map={
            "Urban - Tier 1": "#FF6B6B",
            "Urban - Tier 2": "#FFD166",
            "Rural / Semi-Urban": "#06D6A0",
        },
    )
    fig.update_layout(height=500)
    dual_view("🏆 Top-10 RTO Leaderboard", fig, top_df, key="rto_top10")

st.divider()

# ----- Panel 2: Tier mix over the slice -------------------------------------
agg_tier = Q.rto_aggregate_by(by="tier", col_dim=col_dim, **q_kwargs)
if not agg_tier.empty:
    fig = px.bar(
        agg_tier, x="col_value", y="value", color="grp", barmode="stack",
        labels={"col_value": DIM_LABELS.get(col_dim, col_dim),
                "value": "Registrations", "grp": "Tier"},
        color_discrete_map={
            "Urban - Tier 1": "#FF6B6B",
            "Urban - Tier 2": "#FFD166",
            "Rural / Semi-Urban": "#06D6A0",
        },
    )
    dual_view(f"Urban / Rural split by {DIM_LABELS.get(col_dim, col_dim)}",
              fig, agg_tier.rename(columns={"grp": "tier"}),
              key="rto_tier_mix")

st.divider()

# ----- Panel 3: Region heat-strip -------------------------------------------
agg_region = Q.rto_aggregate_by(by="region", col_dim=col_dim, **q_kwargs)
if not agg_region.empty:
    fig = px.bar(
        agg_region, x="col_value", y="value", color="grp", barmode="group",
        labels={"col_value": DIM_LABELS.get(col_dim, col_dim),
                "value": "Registrations", "grp": "Region"},
    )
    dual_view(f"Regional breakdown by {DIM_LABELS.get(col_dim, col_dim)}",
              fig, agg_region.rename(columns={"grp": "region"}),
              key="rto_region")

st.divider()

# ----- Panel 4: Full pivoted data grid --------------------------------------
st.subheader("📋 Full RTO pivot (current filters)")
pivot = Q.rto_pivot(col_dim=col_dim, **q_kwargs)
if pivot.empty:
    st.info("No rows to show.")
else:
    st.caption(f"{len(pivot):,} RTOs × {len(pivot.columns)} columns")
    search = st.text_input("Search RTO / state / region / tier", key="rto_pivot_search")
    view = pivot
    if search:
        m = view.apply(lambda c: c.astype(str).str.contains(search, case=False, na=False))
        view = view[m.any(axis=1)]
    st.dataframe(view, use_container_width=True, height=460)
    st.download_button(
        "⬇️ Download full pivot as CSV",
        data=view.to_csv(index=False).encode("utf-8"),
        file_name=f"rto_pivot_{col_dim}_{year}.csv",
        mime="text/csv",
        use_container_width=True,
    )
