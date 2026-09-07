"""Forge-style DuckDB warehouse: land raw frames, read-only SQL sandbox."""

from __future__ import annotations

import re
from typing import Final

import pandas as pd

_FORBIDDEN_SQL: Final[re.Pattern[str]] = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|COPY|PRAGMA|EXPORT|IMPORT|INSTALL|LOAD)\b",
    re.IGNORECASE,
)


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", name)


def connect():
    import duckdb

    return duckdb.connect(database=":memory:")


def register_tables(con, tables: dict[str, pd.DataFrame]) -> list[str]:
    names: list[str] = []
    for name, df in tables.items():
        if not isinstance(df, pd.DataFrame):
            continue
        if df.shape[1] == 0:
            continue
        safe = _safe_name(name)
        con.register(safe, df)
        names.append(safe)
    return names


def run_sql(query: str, tables: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, str]:
    """Read-only SELECT over named DataFrames. DuckDB first, pandas fallback (Forge v2)."""
    q = (query or "").strip().rstrip(";")
    if not q:
        raise ValueError("Empty SQL")
    if _FORBIDDEN_SQL.search(q):
        raise ValueError("Only read-only SELECT queries are allowed")

    frames = {name: df for name, df in tables.items() if isinstance(df, pd.DataFrame)}
    last_err = ""
    try:
        con = connect()
        register_tables(con, frames)
        return con.execute(q).df(), "duckdb"
    except ImportError:
        last_err = "duckdb not installed"
    except Exception as exc:
        last_err = str(exc)

    m = re.match(
        r"SELECT\s+\*\s+FROM\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:LIMIT\s+(\d+))?$",
        q,
        re.IGNORECASE,
    )
    if m:
        name, lim = m.group(1), m.group(2)
        if name not in frames:
            matches = [k for k in frames if _safe_name(k) == name]
            if not matches:
                raise KeyError(f"Unknown table '{name}'. Available: {list(frames)}")
            name = matches[0]
        out = frames[name]
        if lim:
            out = out.head(int(lim))
        return out.copy(), "pandas"
    raise ValueError(f"SQL failed ({last_err}). Use SELECT … FROM <table>.")
