"""FastAPI service exposing Vahan analytics — consumed by the Telegram bot.

Run:
    uvicorn api.main:app --reload --port 8000

Endpoints (all JSON):
    GET  /health
    GET  /stats
    GET  /years
    GET  /dim/{row_dim}                 -> list distinct row values
    GET  /pivot?row_dim&col_dim&year    -> wide-form pivot
    GET  /top?row_dim&col_dim&year&n    -> top-N rows
    GET  /trend?year&state=             -> monthly trend (country or one state)
    GET  /maker?maker&year&month        -> single cell lookup
    POST /refresh                       -> re-ingest the YTD folder
    GET  /export.xlsx?year              -> stream the unified master workbook
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from io import BytesIO

from core import ingest, queries as Q, export
from core.config import ROW_DIMS, COL_DIMS

app = FastAPI(
    title="Vahan Auto-Analytics API",
    version="1.0",
    description="Backend used by the Streamlit dashboard and the Telegram bot."
)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/stats")
def stats():
    return ingest.stats()


@app.get("/years")
def years():
    return Q.available_years()


@app.get("/dim/{row_dim}")
def dim(row_dim: str):
    if row_dim not in ROW_DIMS:
        raise HTTPException(404, f"Unknown dim. Pick from {ROW_DIMS}")
    return Q.list_dim_values(row_dim)


@app.get("/pivot")
def pivot(row_dim: str, col_dim: str, year: int | None = None):
    if row_dim not in ROW_DIMS or col_dim not in COL_DIMS:
        raise HTTPException(400, "Bad dim")
    df = Q.pivot(row_dim, col_dim, years=[year] if year else None)
    return JSONResponse(df.reset_index().to_dict(orient="records"))


@app.get("/top")
def top(row_dim: str, col_dim: str = "MonthWise", year: int | None = None, n: int = 10):
    df = Q.top_n(row_dim, col_dim, n=n, years=[year] if year else None)
    return JSONResponse(df.reset_index().to_dict(orient="records"))


@app.get("/trend")
def trend(year: int, state: str | None = None):
    df = Q.monthly_trend(year, row_value=state)
    return JSONResponse(df.astype({"month": str}).to_dict(orient="records"))


@app.get("/maker")
def maker(maker: str, year: int, month: str):
    val = Q.maker_in_month(maker, year, month)
    if val is None:
        raise HTTPException(404, "No data for that maker/month")
    return {"maker": maker, "year": year, "month": month.upper(), "value": val}


@app.get("/marketshare")
def marketshare(row_dim: str, col_dim: str = "MonthWise", year: int | None = None, n: int = 10):
    df = Q.market_share(row_dim, col_dim, n=n, years=[year] if year else None)
    return JSONResponse(df.reset_index().to_dict(orient="records"))


@app.post("/refresh")
def refresh():
    return ingest.refresh_ytd()


@app.get("/export.xlsx")
def export_xlsx(year: int | None = None):
    data = export.build_workbook(year)
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=Vahan_Master_{year or 'latest'}.xlsx"},
    )
