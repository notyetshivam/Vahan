"""Vahan Auto-Analytics Hub — Streamlit entrypoint.

The sidebar handles data refresh + global filters; pages live in app/pages/.
Run from project root:

    streamlit run app/streamlit_app.py
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from core import ingest  # noqa: E402
from core.config import YTD_DIR  # noqa: E402

st.set_page_config(
    page_title="Vahan Auto-Analytics Hub",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🚗 Vahan Auto-Analytics Hub")
st.caption("Vehicle registration intelligence — ingest, explore, export, and (soon) chat.")


def _stats():
    try:
        return ingest.stats()
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


@st.cache_resource(show_spinner="First-time setup: ingesting Vahan data…")
def _bootstrap():
    """On first run (e.g. fresh Streamlit Cloud container) seed DuckDB from data/ytd/."""
    s = ingest.stats()
    if s.get("rows", 0) == 0:
        ingest.refresh_ytd()
    return ingest.stats()


_bootstrap()


with st.sidebar:
    st.header("Data status")
    s = _stats()
    if "error" in s:
        st.error(s["error"])
    else:
        c1, c2 = st.columns(2)
        c1.metric("Files", s.get("files", 0))
        c2.metric("Rows", f"{s.get('rows', 0):,}")
        st.caption(
            f"Years: {s.get('year_min', '-')}–{s.get('year_max', '-')}\n\n"
            f"Last ingest: {s.get('last_run', 'never')}"
        )

    st.divider()
    st.subheader("Refresh")
    st.code(str(YTD_DIR), language="text")
    st.caption("Drop the 38 `Vahan_*_Unified.xlsx` files in the folder above.")
    if st.button("🔁 Re-ingest YTD folder", use_container_width=True):
        with st.spinner("Parsing 38 files…"):
            res = ingest.refresh_ytd()
        st.success(f"Loaded {res['files']} files / {res['rows']:,} rows")
        st.rerun()

    st.divider()
    st.subheader("Year-end archival")
    yr = st.number_input("Year to freeze into history", value=2025, step=1)
    if st.button("📦 Archive year"):
        path = ingest.archive_year(int(yr))
        st.success(f"Archived to {path.name}")
        st.rerun()

st.markdown(
    """
### Welcome
Use the **left navigation** to jump between modules:

- **Executive Summary** — KPIs, monthly trend, top movers.
- **Maker Intelligence** — Drill into Maruti, Hyundai, Tata, anyone.
- **Geographic Trends** — State-level leaderboards and adoption stories.
- **Fuel & Emissions** — ICE vs EV, BS-VI rollout, fuel mix.
- **Vehicle Deep-Dive** — Slice by class / category / category group.
- **Export** — Generate the unified master Excel workbook.

> Data sits in DuckDB (`data/vahan.duckdb`). The same query layer powers the
> upcoming Telegram bot, so anything you see here can be asked of the bot too.
"""
)
