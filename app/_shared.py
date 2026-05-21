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


def dual_view(title: str, fig, df, *, key: str, sortable_default: str | None = None) -> None:
    """Render a Plotly figure on top + a sortable/searchable/downloadable data grid below.

    PRD v2 § Feature 4 — every panel must expose both graphical and numerical views.
    """
    import streamlit as st
    st.subheader(title)
    st.plotly_chart(fig, use_container_width=True, key=f"{key}_chart")
    with st.expander("🔎 Numerical view (sort, search, download CSV)", expanded=False):
        search = st.text_input("Search rows", key=f"{key}_search", placeholder="filter substring…")
        view_df = df
        if search:
            mask = df.apply(lambda c: c.astype(str).str.contains(search, case=False, na=False))
            view_df = df[mask.any(axis=1)]
        st.dataframe(view_df, use_container_width=True, height=380)
        csv = view_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download CSV", csv,
            file_name=f"{key}.csv", mime="text/csv",
            key=f"{key}_dl", use_container_width=True,
        )


def cascading_rto_filters(*, key_prefix: str = "rto") -> dict:
    """Sidebar widget: Region → State → Tier cascading multi-selects.

    Returns a dict of selected regions/states/tiers (None means "no filter").
    """
    import streamlit as st
    from core import queries as Q

    st.sidebar.markdown("### 🎯 RTO filters")
    all_regions = Q.list_regions()
    regions = st.sidebar.multiselect(
        "Region", all_regions, key=f"{key_prefix}_regions",
        help="North / South / East / West / Central / North-East",
    )
    states_pool = Q.list_states_in_regions(regions if regions else None)
    states = st.sidebar.multiselect(
        "State", states_pool, key=f"{key_prefix}_states",
        help="Dynamically narrowed by the regions you picked.",
    )
    all_tiers = Q.list_tiers()
    tiers = st.sidebar.multiselect(
        "Urban / Rural tier", all_tiers, key=f"{key_prefix}_tiers",
        help="Tier 1 / Tier 2 / Rural-SemiUrban (from stratification matrix).",
    )
    return {
        "regions": regions or None,
        "states": states or None,
        "tiers": tiers or None,
    }
