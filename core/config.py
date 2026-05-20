"""Central paths + constants for Vahan Auto-Analytics Hub."""
from __future__ import annotations
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("VAHAN_DATA_DIR", ROOT / "data"))
YTD_DIR = DATA_DIR / "ytd"
HISTORICAL_DIR = DATA_DIR / "historical"
DB_PATH = DATA_DIR / "vahan.duckdb"

for p in (YTD_DIR, HISTORICAL_DIR):
    p.mkdir(parents=True, exist_ok=True)

# 7 row dimensions x several column dimensions = 38 files.
ROW_DIMS = ["State", "Maker", "Norms", "VehicleClass", "VehicleCategory",
            "VehicleCategoryGroup", "Fuel"]
COL_DIMS = ["CalendarYear", "FinancialYear", "MonthWise",
            "VehicleCategoryGroup", "Norms", "VehicleClass", "VehicleCategory"]

# Human-friendly labels for the UI.
DIM_LABELS = {
    "State": "State", "Maker": "Maker", "Norms": "Emission Norms",
    "VehicleClass": "Vehicle Class", "VehicleCategory": "Vehicle Category",
    "VehicleCategoryGroup": "Vehicle Category Group", "Fuel": "Fuel",
    "CalendarYear": "Calendar Year", "FinancialYear": "Financial Year",
    "MonthWise": "Month",
}

MONTHS_ORDER = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

# Vehicle Category Group hierarchy (parent -> children).
CATEGORY_GROUP_HIERARCHY = {
    "TWO WHEELER": ["2WIC", "2WN", "2WT"],
    "THREE WHEELER": ["3WIC", "3WN", "3WT", "3WT-CEV"],
    "FOUR WHEELER": ["4WIC", "LMV", "MMV", "HMV"],
    "LMV": ["LMV", "LPV", "LGV"],
    "MMV": ["MMV", "MPV", "MGV"],
    "HMV": ["HMV", "HPV", "HGV"],
}

# Fuels typically considered "Green".
GREEN_FUELS = {"ELECTRIC(BOV)", "ELECTRIC", "PURE EV", "PLUG-IN HYBRID EV",
               "STRONG HYBRID EV", "FUEL CELL HYDROGEN", "CNG ONLY",
               "LNG", "ETHANOL", "METHANOL", "SOLAR"}
