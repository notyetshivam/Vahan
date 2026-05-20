"""Helpers shared by Streamlit pages: path bootstrap, formatters, sidebar year picker."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from core import queries as Q  # noqa: E402


def page_setup(title: str, icon: str = "📊") -> None:
    st.set_page_config(page_title=f"{title} · Vahan", page_icon=icon, layout="wide")
    st.title(f"{icon} {title}")


def year_picker(label: str = "Year", default: int | None = None) -> int | None:
    years = Q.available_years()
    if not years:
        st.warning("No data ingested yet. Use the sidebar on the home page to refresh.")
        return None
    default = default or years[-1]
    return st.sidebar.selectbox(label, years, index=years.index(default))


def fmt_int(n: float | int | None) -> str:
    if n is None:
        return "—"
    return f"{int(n):,}"


def fmt_pct(p: float | None) -> str:
    if p is None:
        return "—"
    return f"{p:+.2f}%"
