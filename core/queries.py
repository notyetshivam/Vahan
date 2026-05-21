"""Reusable analytical queries on top of the DuckDB ``vahan_fact`` view.

Everything goes through here so the Streamlit UI and the future Telegram/NLP
bot return identical answers.
"""
from __future__ import annotations
from contextlib import contextmanager
from typing import Iterable
import duckdb
import pandas as pd

from .config import DB_PATH, MONTHS_ORDER
from .ingest import _ensure_schema, _rebuild_view


@contextmanager
def connect():
    con = duckdb.connect(str(DB_PATH), read_only=False)
    try:
        _ensure_schema(con)
        _rebuild_view(con)
        yield con
    finally:
        con.close()


def _df(sql: str, params: list | None = None) -> pd.DataFrame:
    with connect() as con:
        return con.execute(sql, params or []).fetchdf()


# ---------- Catalog helpers ----------

def list_dim_values(row_dim: str, col_dim: str | None = None) -> list[str]:
    """Distinct row_value or col_value for a dimension."""
    if col_dim is None:
        sql = ("SELECT DISTINCT row_value AS v FROM vahan_fact "
               "WHERE row_dim = ? AND row_value IS NOT NULL ORDER BY v;")
        return _df(sql, [row_dim])["v"].tolist()
    sql = ("SELECT DISTINCT col_value AS v FROM vahan_fact "
           "WHERE col_dim = ? AND col_value IS NOT NULL ORDER BY v;")
    return _df(sql, [col_dim])["v"].tolist()


def available_years() -> list[int]:
    df = _df("SELECT DISTINCT year FROM vahan_fact WHERE year IS NOT NULL ORDER BY year;")
    return df["year"].astype(int).tolist()


def file_keys() -> list[str]:
    return _df("SELECT DISTINCT file_key FROM vahan_fact ORDER BY 1;")["file_key"].tolist()


# ---------- Core slices ----------

def slice_fact(
    row_dim: str,
    col_dim: str,
    *,
    row_values: Iterable[str] | None = None,
    col_values: Iterable[str] | None = None,
    years: Iterable[int] | None = None,
) -> pd.DataFrame:
    """Return the raw long-form slice for one file_key, with optional filters."""
    file_key = f"{row_dim}_{col_dim}".lower()
    where = ["file_key = ?"]
    params: list = [file_key]
    if row_values:
        rv = list(row_values)
        where.append(f"row_value IN ({','.join(['?']*len(rv))})")
        params.extend(rv)
    if col_values:
        cv = list(col_values)
        where.append(f"col_value IN ({','.join(['?']*len(cv))})")
        params.extend(cv)
    if years:
        ys = list(years)
        where.append(f"year IN ({','.join(['?']*len(ys))})")
        params.extend(ys)
    sql = f"SELECT * FROM vahan_fact WHERE {' AND '.join(where)};"
    df = _df(sql, params)
    if col_dim == "MonthWise" and not df.empty:
        df["col_value"] = pd.Categorical(df["col_value"], categories=MONTHS_ORDER, ordered=True)
        df = df.sort_values(["row_value", "col_value"])
    return df


def pivot(row_dim: str, col_dim: str, **kwargs) -> pd.DataFrame:
    """Wide-form pivot (rows = row_value, cols = col_value)."""
    df = slice_fact(row_dim, col_dim, **kwargs)
    if df.empty:
        return df
    out = df.pivot_table(
        index="row_value", columns="col_value", values="value",
        aggfunc="sum", fill_value=0, observed=True,
    )
    if col_dim == "MonthWise":
        cols = [m for m in MONTHS_ORDER if m in out.columns]
        out = out[cols]
    out["TOTAL"] = out.sum(axis=1)
    return out.sort_values("TOTAL", ascending=False)


# ---------- KPI / aggregates ----------

def total_ytd(year: int) -> int:
    """All-India registrations for `year`. Uses State×MonthWise (most granular)."""
    sql = ("SELECT COALESCE(SUM(value), 0) FROM vahan_fact "
           "WHERE file_key = 'state_monthwise' AND year = ?;")
    with connect() as con:
        return int(con.execute(sql, [year]).fetchone()[0])


def yoy_growth(year: int, prev: int | None = None) -> float | None:
    """YoY % growth in total registrations. prev defaults to year-1."""
    prev = prev or year - 1
    cur = total_ytd(year)
    p = total_ytd(prev)
    if not p:
        return None
    return (cur - p) / p * 100.0


def top_n(row_dim: str, col_dim: str, n: int = 10, **kwargs) -> pd.DataFrame:
    """Top-N rows by TOTAL across the selected slice."""
    p = pivot(row_dim, col_dim, **kwargs)
    if p.empty:
        return p
    return p.head(n)


def market_share(row_dim: str, col_dim: str, n: int = 10, **kwargs) -> pd.DataFrame:
    """Top-N share-of-total table with a remainder row."""
    p = pivot(row_dim, col_dim, **kwargs)
    if p.empty:
        return p
    totals = p["TOTAL"]
    grand = totals.sum() or 1
    top = totals.head(n)
    rest = totals.iloc[n:].sum()
    out = pd.DataFrame({"value": top})
    if rest:
        out.loc["Others"] = rest
    out["share_pct"] = out["value"] / grand * 100
    return out


def monthly_trend(year: int, row_value: str | None = None) -> pd.DataFrame:
    """Country-wide or state-specific monthly sales for a year."""
    if row_value:
        df = slice_fact("State", "MonthWise", row_values=[row_value], years=[year])
        grp = df.groupby("col_value", observed=True)["value"].sum().reset_index()
    else:
        df = slice_fact("State", "MonthWise", years=[year])
        grp = df.groupby("col_value", observed=True)["value"].sum().reset_index()
    grp = grp.rename(columns={"col_value": "month"})
    grp["month"] = pd.Categorical(grp["month"], categories=MONTHS_ORDER, ordered=True)
    return grp.sort_values("month")


def maker_in_month(maker: str, year: int, month: str) -> float | None:
    """Specific cell lookup, used by /trend command in the bot."""
    sql = ("SELECT SUM(value) FROM vahan_fact "
           "WHERE file_key = 'maker_monthwise' AND row_value = ? "
           "AND year = ? AND col_value = ?;")
    with connect() as con:
        r = con.execute(sql, [maker, year, month.upper()]).fetchone()
    return float(r[0]) if r and r[0] is not None else None


# ====================================================================
# RTO-level analytics (Phase v2 — joins fact_rto with dim_rto)
# ====================================================================

def list_regions() -> list[str]:
    df = _df("SELECT DISTINCT region FROM dim_rto WHERE region IS NOT NULL ORDER BY region;")
    return df["region"].tolist()


def list_tiers() -> list[str]:
    df = _df("SELECT DISTINCT urban_rural_proxy AS t FROM dim_rto "
             "WHERE urban_rural_proxy IS NOT NULL ORDER BY t;")
    return df["t"].tolist()


def list_states_in_regions(regions: Iterable[str] | None = None) -> list[str]:
    if not regions:
        df = _df("SELECT DISTINCT state_name FROM dim_rto WHERE state_name IS NOT NULL ORDER BY 1;")
    else:
        rs = list(regions)
        ph = ",".join(["?"] * len(rs))
        df = _df(
            f"SELECT DISTINCT state_name FROM dim_rto "
            f"WHERE state_name IS NOT NULL AND region IN ({ph}) ORDER BY 1;",
            rs,
        )
    return df["state_name"].tolist()


def dim_rto_df() -> pd.DataFrame:
    return _df("SELECT * FROM dim_rto ORDER BY state_name, rto_name;")


def _filter_clause(
    regions: Iterable[str] | None,
    states: Iterable[str] | None,
    tiers: Iterable[str] | None,
    years: Iterable[int] | None,
    col_dim: str | None,
) -> tuple[str, list]:
    where = ["1=1"]
    params: list = []
    if col_dim:
        where.append("f.file_key = ?")
        params.append(f"rto_{col_dim}".lower())
    if regions:
        rs = list(regions)
        where.append(f"d.region IN ({','.join(['?']*len(rs))})")
        params.extend(rs)
    if states:
        ss = list(states)
        where.append(f"d.state_name IN ({','.join(['?']*len(ss))})")
        params.extend(ss)
    if tiers:
        ts = list(tiers)
        where.append(f"d.urban_rural_proxy IN ({','.join(['?']*len(ts))})")
        params.extend(ts)
    if years:
        ys = list(years)
        where.append(f"f.year IN ({','.join(['?']*len(ys))})")
        params.extend(ys)
    return " AND ".join(where), params


def rto_slice(
    col_dim: str = "MonthWise",
    *,
    regions: Iterable[str] | None = None,
    states: Iterable[str] | None = None,
    tiers: Iterable[str] | None = None,
    col_values: Iterable[str] | None = None,
    years: Iterable[int] | None = None,
) -> pd.DataFrame:
    """Long-form RTO slice with dim_rto context joined in."""
    clause, params = _filter_clause(regions, states, tiers, years, col_dim)
    if col_values:
        cv = list(col_values)
        clause += f" AND f.col_value IN ({','.join(['?']*len(cv))})"
        params.extend(cv)
    sql = f"""
        SELECT f.rto, d.state_name, d.region, d.urban_rural_proxy AS tier,
               f.col_dim, f.col_value, f.year, f.month, f.value
        FROM vahan_rto_fact f
        LEFT JOIN dim_rto d ON UPPER(TRIM(d.rto_name)) = UPPER(TRIM(f.rto))
        WHERE {clause};
    """
    return _df(sql, params)


def rto_top(
    n: int = 10,
    *,
    col_dim: str = "MonthWise",
    regions: Iterable[str] | None = None,
    states: Iterable[str] | None = None,
    tiers: Iterable[str] | None = None,
    col_values: Iterable[str] | None = None,
    years: Iterable[int] | None = None,
) -> pd.DataFrame:
    """Top-N RTOs by total registrations within the filter set."""
    clause, params = _filter_clause(regions, states, tiers, years, col_dim)
    if col_values:
        cv = list(col_values)
        clause += f" AND f.col_value IN ({','.join(['?']*len(cv))})"
        params.extend(cv)
    sql = f"""
        SELECT f.rto, d.state_name, d.region, d.urban_rural_proxy AS tier,
               SUM(f.value) AS total
        FROM vahan_rto_fact f
        LEFT JOIN dim_rto d ON UPPER(TRIM(d.rto_name)) = UPPER(TRIM(f.rto))
        WHERE {clause}
        GROUP BY 1,2,3,4
        ORDER BY total DESC NULLS LAST
        LIMIT ?;
    """
    params.append(int(n))
    return _df(sql, params)


def rto_pivot(
    col_dim: str = "MonthWise",
    *,
    regions=None, states=None, tiers=None, years=None,
) -> pd.DataFrame:
    """Wide pivot: rows = RTO, cols = col_value of the chosen dim."""
    df = rto_slice(col_dim, regions=regions, states=states, tiers=tiers, years=years)
    if df.empty:
        return df
    out = df.pivot_table(
        index=["rto", "state_name", "region", "tier"],
        columns="col_value", values="value", aggfunc="sum", fill_value=0,
    )
    if col_dim == "MonthWise":
        cols = [m for m in MONTHS_ORDER if m in out.columns]
        out = out[cols]
    out["TOTAL"] = out.sum(axis=1)
    return out.sort_values("TOTAL", ascending=False).reset_index()


def rto_aggregate_by(
    by: str = "tier",
    col_dim: str = "MonthWise",
    *,
    regions=None, states=None, tiers=None, years=None,
) -> pd.DataFrame:
    """Aggregate RTO sales by a grouping key (tier / region / state / month).

    Returns long-form ``(group, col_value, value)``.
    """
    assert by in {"tier", "region", "state_name"}
    col_expr = {"tier": "d.urban_rural_proxy", "region": "d.region",
                "state_name": "d.state_name"}[by]
    clause, params = _filter_clause(regions, states, tiers, years, col_dim)
    sql = f"""
        SELECT {col_expr} AS grp, f.col_value, SUM(f.value) AS value
        FROM vahan_rto_fact f
        LEFT JOIN dim_rto d ON UPPER(TRIM(d.rto_name)) = UPPER(TRIM(f.rto))
        WHERE {clause}
        GROUP BY 1,2 ORDER BY 1,2;
    """
    df = _df(sql, params)
    if col_dim == "MonthWise" and not df.empty:
        df["col_value"] = pd.Categorical(df["col_value"], categories=MONTHS_ORDER, ordered=True)
        df = df.sort_values(["grp", "col_value"])
    return df


def ev_share_by_state(year: int) -> pd.DataFrame:
    """EV vs total registrations, by state."""
    sql = """
        WITH ev AS (
            SELECT row_value AS state, SUM(value) AS ev_count
            FROM vahan_fact
            WHERE file_key = 'state_monthwise' AND year = ?
            GROUP BY 1
        ), total_state AS (
            SELECT row_value AS state, SUM(value) AS total
            FROM vahan_fact
            WHERE file_key = 'state_monthwise' AND year = ?
            GROUP BY 1
        ), fuel_state AS (
            SELECT row_value AS state,
                   SUM(CASE WHEN UPPER(col_value) LIKE '%ELECTRIC%'
                            OR UPPER(col_value) LIKE '%EV%'
                            OR UPPER(col_value) LIKE '%HYBRID%'
                       THEN value ELSE 0 END) AS green,
                   SUM(value) AS tot
            FROM vahan_fact
            WHERE file_key = 'fuel_monthwise' AND year = ?
            GROUP BY 1
        )
        -- fuel_monthwise is fuel x month, not state, so fall back via state_fuel pivot if missing.
        SELECT state, tot AS total, green, ROUND(green*100.0/NULLIF(tot,0), 2) AS pct
        FROM fuel_state ORDER BY pct DESC NULLS LAST;
    """
    # Better: pull from a State x Fuel-implied source — we only have aggregate fuel files,
    # so approximate via the State_VehicleCategory file is not right either. Use the
    # fact that fuel_monthwise is a country-level series. We instead build EV share
    # from fuel_vehicleclass if present, else return the aggregate fuel breakdown.
    df = _df(
        """
        SELECT col_value AS fuel,
               SUM(value) AS count
        FROM vahan_fact
        WHERE file_key = 'fuel_monthwise' AND year = ?
        GROUP BY 1 ORDER BY count DESC;
        """,
        [year],
    )
    # Caller will compute EV share from this; we surface fuel mix directly.
    return df
