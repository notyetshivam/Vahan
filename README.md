# Vahan Auto-Analytics Hub

End-to-end analytics for India's vehicle registration data (Vahan). Ingests the
38 `Vahan_*_Unified.xlsx` cross-tabs, stores them in DuckDB, exposes the
analytics through both an interactive **Streamlit** dashboard and a JSON
**FastAPI** service — so the Phase-2 Telegram bot is a thin wrapper around the
same query layer.

```
+--------------------+         +---------------------+        +---------------------+
|  data/ytd/*.xlsx   |  -->    |  core/ingest.py     |  -->   |  DuckDB             |
+--------------------+         +---------------------+        +----------+----------+
                                                                         |
                                       core/queries.py  <----------------+
                                       core/export.py
                                              |
                +-----------------------------+-----------------------------+
                |                             |                             |
        Streamlit (app/)              FastAPI (api/)              Telegram bot (bot/)
```

## Project layout

```
Z:\Vahan\
├── requirements.txt
├── README.md
├── data/
│   ├── ytd/             <- drop the 38 Vahan_*_Unified.xlsx here
│   ├── historical/      <- year-end parquet snapshots
│   └── vahan.duckdb     <- created on first ingest
├── core/                <- single source of truth (used by UI, API, bot)
│   ├── config.py
│   ├── parser.py        <- messy xlsx headers + Indian numbers -> long form
│   ├── ingest.py        <- folder-watch ingestion into DuckDB
│   ├── queries.py       <- YoY, MoM, top-N, market share, lookups
│   └── export.py        <- unified master xlsx
├── app/                 <- Streamlit UI
│   ├── streamlit_app.py
│   ├── _shared.py
│   └── pages/
│       ├── 1_Executive_Summary.py
│       ├── 2_Maker_Intelligence.py
│       ├── 3_Geographic.py
│       ├── 4_Fuel_Emissions.py
│       ├── 5_Vehicle_Deep_Dive.py
│       └── 6_Export.py
├── api/
│   └── main.py          <- FastAPI: /pivot, /top, /trend, /maker, /export.xlsx, /refresh
└── bot/
    └── README.md        <- Phase-2 Telegram bot blueprint
```

## Setup

```powershell
cd Z:\Vahan
python -m pip install -r requirements.txt
```

## Data refresh (folder-watch model)

1. Drop the 38 `Vahan_*_Unified.xlsx` files into `data/ytd/`.
2. Ingest:
   ```powershell
   python -m core.ingest
   ```
   or click **🔁 Re-ingest YTD folder** in the dashboard sidebar.

YTD is treated as a *temporary staging* table — every refresh fully overwrites
it. At year-end, freeze the current year into the historical vault:

```python
from core.ingest import archive_year
archive_year(2026)        # moves 2026 rows -> data/historical/2026.parquet
```

After that, the row is part of the permanent historical record and the YTD
table is empty until the next year's data arrives.

## Run the dashboard

```powershell
streamlit run app/streamlit_app.py
```

Open http://localhost:8501. The six PRD tabs auto-appear in the left nav.

## Run the API (used by the Telegram bot)

```powershell
uvicorn api.main:app --reload --port 8000
```

Then `http://localhost:8000/docs` for the OpenAPI playground.

Key endpoints:

| Method | Path                                       | Purpose                           |
|--------|--------------------------------------------|-----------------------------------|
| GET    | `/health`                                  | Liveness                          |
| GET    | `/stats`                                   | Rows / files / last ingest        |
| GET    | `/years`                                   | Years available                   |
| GET    | `/dim/{State\|Maker\|Fuel\|...}`           | Distinct values                   |
| GET    | `/pivot?row_dim&col_dim&year`              | Wide-form pivot                   |
| GET    | `/top?row_dim&col_dim&year&n`              | Top-N rows                        |
| GET    | `/marketshare?row_dim&col_dim&year&n`      | Share-of-total                    |
| GET    | `/trend?year[&state=...]`                  | Monthly trajectory                |
| GET    | `/maker?maker&year&month`                  | Single-cell lookup                |
| POST   | `/refresh`                                 | Re-ingest YTD folder              |
| GET    | `/export.xlsx?year`                        | Stream the unified master report  |

## Deployment (public sharing)

Both halves run on free tiers:

- **Streamlit** → push to GitHub, deploy on [Streamlit Cloud](https://streamlit.io/cloud) (1-click, public URL).
- **FastAPI** → deploy on Render / Fly.io / Railway as a separate service.
  Point the bot at the API URL via an env var. Mount a small persistent disk
  for `data/` so the DuckDB file and parquet history survive restarts.

## Data model

Every file is normalised into one long fact table:

```
vahan_fact(
    file_key,    -- e.g. 'state_monthwise', 'maker_vehiclecategory'
    row_dim,     -- 'State'
    row_value,   -- 'MAHARASHTRA'
    col_dim,     -- 'MonthWise'
    col_value,   -- 'APR'
    year,        -- 2026
    month,       -- 'APR' (NULL unless col_dim = MonthWise)
    value        -- 95277.0
)
```

`vahan_fact` is a *view* unioning the live YTD table + all historical parquet
years. Queries are file-keyed to prevent double-counting across overlapping
slices.

## Phase 2 — Telegram bot

See [`bot/README.md`](bot/README.md). The bot will:

1. Take a natural-language Telegram message.
2. Have an LLM classify it into a whitelisted API call (`/top`, `/trend`, …).
3. Format the JSON response as a markdown reply, with an optional Plotly PNG.
4. Hard-refuse anything off-topic via a system prompt guardrail.

The query layer is already abstracted exactly for this — no business-logic
duplication required.
