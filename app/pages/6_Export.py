"""Tab 6 — Unified Master Excel export."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from app._shared import page_setup, year_picker
from core import export

page_setup("Unified Master Report", "📤")

year = year_picker("Year")
if year is None:
    st.stop()

st.markdown(
    """
This generates a **single .xlsx** containing:

- **Summary** sheet: KPIs, top-10s, fuel/category breakdowns.
- One sheet per available `(row dim × column dim)` pivot — all the master datasets, cleaned.
"""
)

if st.button("⚙️ Build workbook", type="primary", use_container_width=True):
    with st.spinner("Building report…"):
        data = export.build_workbook(int(year))
    st.success(f"Generated {len(data)/1024:.0f} KB workbook.")
    st.download_button(
        "⬇️ Download Vahan_Master_Report.xlsx",
        data=data,
        file_name=f"Vahan_Master_Report_{year}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
