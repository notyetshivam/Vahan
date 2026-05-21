"""Ingest unified Vahan xlsx files into DuckDB.

Storage strategy
----------------
* Historical Vault: ``data/historical/{year}.parquet`` — finalized completed years.
* Active YTD: DuckDB table ``vahan_fact_ytd`` — overwritten on every refresh.
* Unified view ``vahan_fact`` UNIONs all historical parquet years + ytd table.

Run ``python -m core.ingest`` to refresh.
"""
from __future__ import annotations
from pathlib import Path
import datetime as dt
import duckdb
import pandas as pd

from .config import (
    DB_PATH, YTD_DIR, RTO_DIR, HISTORICAL_DIR,
    EXPECTED_TIER_COUNTS, TIER_DRIFT_THRESHOLD,
)
from .parser import parse_directory
from .rto_parser import parse_rto_directory, load_dim_rto

FACT_COLUMNS = ["file_key", "row_dim", "row_value", "col_dim",
                "col_value", "year", "month", "value"]

RTO_FACT_COLUMNS = ["file_key", "state", "rto", "col_dim",
                    "col_value", "year", "month", "value"]


def _connect() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DB_PATH))


def _ensure_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS vahan_fact_ytd (
            file_key   VARCHAR,
            row_dim    VARCHAR,
            row_value  VARCHAR,
            col_dim    VARCHAR,
            col_value  VARCHAR,
            year       INTEGER,
            month      VARCHAR,
            value      DOUBLE
        );
        CREATE TABLE IF NOT EXISTS vahan_rto_fact_ytd (
            file_key   VARCHAR,
            state      VARCHAR,
            rto        VARCHAR,
            col_dim    VARCHAR,
            col_value  VARCHAR,
            year       INTEGER,
            month      VARCHAR,
            value      DOUBLE
        );
        CREATE TABLE IF NOT EXISTS dim_rto (
            rto_name          VARCHAR PRIMARY KEY,
            state_name        VARCHAR,
            region            VARCHAR,
            urban_rural_proxy VARCHAR
        );
        CREATE TABLE IF NOT EXISTS vahan_ingest_log (
            run_at TIMESTAMP,
            n_files INTEGER,
            n_rows BIGINT,
            note VARCHAR
        );
        """
    )


def _historical_parquets() -> list[Path]:
    return sorted(HISTORICAL_DIR.glob("*.parquet"))


def _rebuild_view(con: duckdb.DuckDBPyConnection) -> None:
    parts = ["SELECT * FROM vahan_fact_ytd"]
    for p in _historical_parquets():
        if p.stem.startswith("rto_"):
            continue  # rto historical handled separately
        parts.append(f"SELECT * FROM read_parquet('{p.as_posix()}')")
    con.execute("DROP VIEW IF EXISTS vahan_fact;")
    con.execute(f"CREATE VIEW vahan_fact AS {' UNION ALL '.join(parts)};")

    rto_parts = ["SELECT * FROM vahan_rto_fact_ytd"]
    for p in _historical_parquets():
        if p.stem.startswith("rto_"):
            rto_parts.append(f"SELECT * FROM read_parquet('{p.as_posix()}')")
    con.execute("DROP VIEW IF EXISTS vahan_rto_fact;")
    con.execute(f"CREATE VIEW vahan_rto_fact AS {' UNION ALL '.join(rto_parts)};")


def refresh_ytd(ytd_dir: Path = YTD_DIR) -> dict:
    """Reparse every unified xlsx in ytd_dir, overwrite the YTD table."""
    con = _connect()
    _ensure_schema(con)

    frames = []
    files = 0
    for path, df in parse_directory(ytd_dir):
        files += 1
        if not df.empty:
            frames.append(df)
    full = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=FACT_COLUMNS)

    con.execute("DELETE FROM vahan_fact_ytd;")
    if not full.empty:
        con.register("incoming_df", full[FACT_COLUMNS])
        con.execute("INSERT INTO vahan_fact_ytd SELECT * FROM incoming_df;")
        con.unregister("incoming_df")

    _rebuild_view(con)
    con.execute(
        "INSERT INTO vahan_ingest_log VALUES (?, ?, ?, ?);",
        [dt.datetime.now(), files, len(full), f"refresh from {ytd_dir}"]
    )
    summary = {"files": files, "rows": len(full), "at": dt.datetime.now().isoformat(timespec="seconds")}
    con.close()
    return summary


def refresh_rto(rto_dir: Path = RTO_DIR) -> dict:
    """Reparse every per-state RTO xlsx + reload dim_rto."""
    con = _connect()
    _ensure_schema(con)

    # --- fact files ---
    frames = []
    files = 0
    for path, df in parse_rto_directory(rto_dir):
        files += 1
        if not df.empty:
            frames.append(df)
    full = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=RTO_FACT_COLUMNS)

    con.execute("DELETE FROM vahan_rto_fact_ytd;")
    if not full.empty:
        con.register("incoming_rto", full[RTO_FACT_COLUMNS])
        con.execute("INSERT INTO vahan_rto_fact_ytd SELECT * FROM incoming_rto;")
        con.unregister("incoming_rto")

    # --- dim_rto (stratification matrix) ---
    dim_result = {"dim_rto_rows": 0, "tier_warning": None}
    matrices = sorted(rto_dir.glob("*Stratification*Matrix*.xlsx"))
    if not matrices:
        matrices = sorted(rto_dir.glob("Consolidated_RTO*.xlsx"))
    if matrices:
        dim_df = load_dim_rto(matrices[0])
        if not dim_df.empty:
            warn = _validate_tier_distribution(dim_df)
            con.execute("DELETE FROM dim_rto;")
            con.register("incoming_dim", dim_df)
            con.execute("INSERT INTO dim_rto SELECT * FROM incoming_dim;")
            con.unregister("incoming_dim")
            dim_result = {"dim_rto_rows": len(dim_df), "tier_warning": warn,
                          "dim_source": matrices[0].name}

    _rebuild_view(con)
    con.execute(
        "INSERT INTO vahan_ingest_log VALUES (?, ?, ?, ?);",
        [dt.datetime.now(), files, len(full),
         f"refresh_rto from {rto_dir} (dim_rto rows={dim_result['dim_rto_rows']})"]
    )
    con.close()
    return {"files": files, "rows": len(full), **dim_result,
            "at": dt.datetime.now().isoformat(timespec="seconds")}


def _validate_tier_distribution(df: pd.DataFrame) -> str | None:
    """Return a human warning string if tier counts drift beyond threshold."""
    if "urban_rural_proxy" not in df.columns:
        return "dim_rto missing urban_rural_proxy column"
    actual = df["urban_rural_proxy"].value_counts(dropna=True).to_dict()
    msgs = []
    for tier, exp in EXPECTED_TIER_COUNTS.items():
        got = int(actual.get(tier, 0))
        if exp == 0:
            continue
        drift = abs(got - exp) / exp
        if drift > TIER_DRIFT_THRESHOLD:
            msgs.append(f"{tier}: expected {exp}, got {got} (Δ {drift:.0%})")
    return "; ".join(msgs) if msgs else None


def archive_year(year: int) -> Path:
    """Freeze the current YTD slice for `year` into the historical vault."""
    con = _connect()
    _ensure_schema(con)
    out = HISTORICAL_DIR / f"{year}.parquet"
    con.execute(
        "COPY (SELECT * FROM vahan_fact_ytd WHERE year = ?) "
        "TO ? (FORMAT PARQUET);",
        [year, out.as_posix()],
    )
    con.execute("DELETE FROM vahan_fact_ytd WHERE year = ?;", [year])
    _rebuild_view(con)
    con.close()
    return out


def stats() -> dict:
    con = _connect()
    _ensure_schema(con)
    _rebuild_view(con)
    try:
        n = con.execute("SELECT COUNT(*) FROM vahan_fact;").fetchone()[0]
        files = con.execute("SELECT COUNT(DISTINCT file_key) FROM vahan_fact;").fetchone()[0]
        years = con.execute("SELECT MIN(year), MAX(year) FROM vahan_fact;").fetchone()
        rto_n = con.execute("SELECT COUNT(*) FROM vahan_rto_fact;").fetchone()[0]
        rto_unique = con.execute("SELECT COUNT(DISTINCT rto) FROM vahan_rto_fact;").fetchone()[0]
        dim_n = con.execute("SELECT COUNT(*) FROM dim_rto;").fetchone()[0]
        last = con.execute(
            "SELECT run_at, n_files, n_rows FROM vahan_ingest_log "
            "ORDER BY run_at DESC LIMIT 1;"
        ).fetchone()
    finally:
        con.close()
    return {
        "rows": n, "files": files,
        "year_min": years[0], "year_max": years[1],
        "rto_rows": rto_n, "rto_unique": rto_unique, "dim_rto_rows": dim_n,
        "last_run": last[0].isoformat(timespec="seconds") if last else None,
        "last_files": last[1] if last else None,
        "last_rows": last[2] if last else None,
    }


if __name__ == "__main__":
    print(refresh_ytd())
    print(refresh_rto())
    print(stats())
