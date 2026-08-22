"""
database.py

Thin SQLite connection helper. Deliberately not an ORM (SQLAlchemy,
etc.) — for a read-only, single-table dataset this size, raw SQL via
sqlite3 is simpler to read, simpler to debug, and there's no real
"model" complexity an ORM would be earning its keep on. If this grows
into a multi-table warehouse with real joins, that calculation changes.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "pipeline" / "data" / "processed" / "incidents.db"


def get_connection():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"No database found at {DB_PATH}. Run the pipeline first: "
            f"cd pipeline && python run_pipeline.py"
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets query results be accessed by column name, not just index
    return conn