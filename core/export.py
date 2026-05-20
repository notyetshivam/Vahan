"""Generate the Unified Master Excel report.

Sheet 1: Summary dashboard (key totals, top-10s, fuel/state breakdowns).
Sheets 2..N: Master datasets — one wide pivot per (row_dim, col_dim) pair.
"""
from __future__ import annotations
from io import BytesIO
from pathlib import Path
import pandas as pd

from . import queries as Q
from .config import ROW_DIMS, COL_DIMS


def _maybe_pivot(row_dim: str, col_dim: str) -> pd.DataFrame | None:
    try:
        df = Q.pivot(row_dim, col_dim)
    except Exception:
        return None
    return None if df.empty else df


def build_workbook(year: int | None = None) -> bytes:
    if year is None:
        years = Q.available_years()
        year = years[-1] if years else None

    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as xl:
        _write_summary(xl, year)
        for r in ROW_DIMS:
            for c in COL_DIMS:
                df = _maybe_pivot(r, c)
                if df is None:
                    continue
                sheet = f"{r}_x_{c}"[:31]
                df.reset_index().to_excel(xl, sheet_name=sheet, index=False)
    return bio.getvalue()


def _write_summary(xl: pd.ExcelWriter, year: int | None) -> None:
    if year is None:
        pd.DataFrame({"info": ["No data ingested yet."]}).to_excel(
            xl, sheet_name="Summary", index=False)
        return

    rows = []
    total = Q.total_ytd(year)
    rows.append(("Year", year))
    rows.append(("Total registrations (YTD)", f"{total:,.0f}"))
    growth = Q.yoy_growth(year)
    rows.append(("YoY growth %", f"{growth:.2f}" if growth is not None else "n/a"))

    pd.DataFrame(rows, columns=["Metric", "Value"]).to_excel(
        xl, sheet_name="Summary", index=False, startrow=0)

    blocks = [
        ("Top 10 States",      Q.top_n("State",  "MonthWise", n=10, years=[year])),
        ("Top 10 Makers",      Q.top_n("Maker",  "MonthWise", n=10, years=[year])),
        ("Fuel mix",           Q.market_share("Fuel", "MonthWise", n=12, years=[year])),
        ("Vehicle Categories", Q.top_n("VehicleCategory", "MonthWise", n=20, years=[year])),
    ]
    row_cursor = len(rows) + 3
    ws = xl.sheets["Summary"]
    for title, df in blocks:
        ws.write(row_cursor, 0, title)
        df.reset_index().to_excel(xl, sheet_name="Summary", index=False, startrow=row_cursor + 1)
        row_cursor += len(df) + 4


def write_to_path(path: Path, year: int | None = None) -> Path:
    path.write_bytes(build_workbook(year))
    return path
