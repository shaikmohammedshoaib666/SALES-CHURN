"""DuckDB landing + SQL slice. Filter 2GB at the warehouse; pandas only sees the slice."""

from __future__ import annotations

import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd

from src.warehouse import _FORBIDDEN_SQL, connect

SLICE_ROW_CAP = 250_000
FEED_HINTS = {
    "customers": ("customer", "master", "account", "client"),
    "sales": ("sale", "order", "txn", "transaction", "invoice"),
    "behavior": ("behav", "churn", "login", "ticket", "engagement"),
}

_SQL_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def classify_member(name: str) -> str | None:
    base = Path(name).name.lower()
    if base.startswith(".") or base.endswith("/"):
        return None
    for feed, hints in FEED_HINTS.items():
        if any(h in base for h in hints):
            return feed
    return None


def extract_zip(
    zip_path: Path,
    dest: Path | None = None,
    *,
    require: tuple[str, ...] = ("customers", "sales"),
) -> dict[str, Path]:
    dest = dest or Path(tempfile.mkdtemp(prefix="keel-zip-"))
    dest.mkdir(parents=True, exist_ok=True)
    found: dict[str, Path] = {}
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            feed = classify_member(info.filename)
            if feed is None:
                continue
            target = dest / Path(info.filename).name
            with zf.open(info) as src, target.open("wb") as out:
                out.write(src.read())
            found[feed] = target
    missing = [f for f in require if f not in found]
    if missing:
        raise ValueError(
            "Zip needs files named like customers*.csv and sales*.csv "
            f"(optional behavior*.csv). Missing: {', '.join(missing)}."
        )
    return found


def absorb_zip(
    collected: dict[str, Path | pd.DataFrame],
    zip_path: Path,
    *,
    slot: str | None = None,
) -> None:
    """Merge a ZIP into an upload bag. A pack ZIP fills empty feeds; a slot ZIP overwrites that feed."""
    if slot is None:
        collected.update(extract_zip(zip_path))
        return
    found = extract_zip(zip_path, require=())
    if slot in found:
        collected[slot] = found[slot]
    if "customers" in found and "sales" in found:
        for feed, path in found.items():
            collected.setdefault(feed, path)
        return
    if slot not in found:
        raise ValueError(
            f"ZIP has no file matching {slot}*.csv. "
            "Name files customers*.csv / sales*.csv (optional behavior*.csv), "
            "or drop a full pack ZIP."
        )


def land_from_collected(collected: dict[str, Path | pd.DataFrame]) -> DuckLanding:
    land = DuckLanding()
    for feed, src in collected.items():
        if feed not in ("customers", "sales", "behavior"):
            continue
        if isinstance(src, pd.DataFrame):
            land.attach_frame(feed, src)
        else:
            land.attach_path(feed, str(src))
    if "sales" not in land.feeds:
        raise ValueError("Sales feed is required.")
    if "customers" not in land.feeds:
        raise ValueError("Customers master is required.")
    return land


def _from_clause(path: str) -> str:
    p = path.replace("'", "''")
    low = p.lower()
    if low.endswith(".parquet"):
        return f"read_parquet('{p}')"
    if low.endswith(".tsv"):
        return f"read_csv_auto('{p}', header=true, sep='\\t', ignore_errors=true)"
    return f"read_csv_auto('{p}', header=true, ignore_errors=true, sample_size=20000)"


class DuckLanding:
    """In-memory DuckDB with views raw_customers / raw_sales / raw_behavior."""

    def __init__(self) -> None:
        self.con = connect()
        try:
            self.con.execute("INSTALL httpfs; LOAD httpfs;")
        except Exception:
            pass
        self.feeds: dict[str, str] = {}

    def attach_path(self, feed: str, path: str) -> None:
        if feed not in ("customers", "sales", "behavior"):
            raise ValueError(f"Unknown feed {feed}")
        view = f"raw_{feed}"
        src = path
        try:
            self.con.execute(f"CREATE OR REPLACE VIEW {view} AS SELECT * FROM {_from_clause(src)}")
            self.con.execute(f"SELECT * FROM {view} LIMIT 1")
        except Exception:
            if str(path).lower().startswith("http"):
                from src.url_ingest import download_to_temp

                src = str(download_to_temp(path))
                self.con.execute(f"CREATE OR REPLACE VIEW {view} AS SELECT * FROM {_from_clause(src)}")
            else:
                raise
        self.feeds[feed] = view

    def attach_frame(self, feed: str, df: pd.DataFrame) -> None:
        view = f"raw_{feed}"
        self.con.register(f"_{view}_df", df)
        self.con.execute(f"CREATE OR REPLACE VIEW {view} AS SELECT * FROM _{view}_df")
        self.feeds[feed] = view

    def rowcount(self, feed: str) -> int:
        view = self.feeds.get(feed)
        if not view:
            return 0
        return int(self.con.execute(f"SELECT COUNT(*) FROM {view}").fetchone()[0])

    def columns(self, feed: str) -> list[str]:
        view = self.feeds.get(feed)
        if not view:
            return []
        rows = self.con.execute(f"DESCRIBE {view}").fetchall()
        return [str(r[0]) for r in rows]

    def preview(self, feed: str, n: int = 20) -> pd.DataFrame:
        view = self.feeds.get(feed)
        if not view:
            return pd.DataFrame()
        return self.con.execute(f"SELECT * FROM {view} LIMIT {int(n)}").df()

    def distinct(self, feed: str, col: str, n: int = 40) -> list[str]:
        view = self.feeds.get(feed)
        if not view or not _SQL_NAME.match(col):
            return []
        try:
            out = self.con.execute(
                f"SELECT DISTINCT CAST({col} AS VARCHAR) AS v FROM {view} WHERE {col} IS NOT NULL LIMIT {int(n)}"
            ).df()
            return [str(x) for x in out["v"].tolist()]
        except Exception:
            return []

    def slice_sql(self, sql: str, cap: int = SLICE_ROW_CAP) -> pd.DataFrame:
        q = (sql or "").strip().rstrip(";")
        if not q:
            raise ValueError("SQL slice is empty")
        if _FORBIDDEN_SQL.search(q):
            raise ValueError("Only read-only SELECT is allowed in the slice.")
        wrapped = f"SELECT * FROM ({q}) AS _slice LIMIT {int(cap)}"
        df = self.con.execute(wrapped).df()
        return df

    def slice_sales(
        self,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        regions: list[str] | None = None,
        customer_ids: list[str] | None = None,
        extra_sql: str | None = None,
        cap: int = SLICE_ROW_CAP,
    ) -> pd.DataFrame:
        if extra_sql and extra_sql.strip():
            return self.slice_sql(extra_sql, cap=cap)
        if "sales" not in self.feeds:
            raise ValueError("No sales feed landed.")
        cols = {c.lower(): c for c in self.columns("sales")}
        date_col = cols.get("order_date") or cols.get("date")
        id_col = cols.get("customer_id") or cols.get("cust_id") or cols.get("customerid")
        region_col = cols.get("region")
        where: list[str] = ["1=1"]
        if date_col and date_from:
            where.append(f"TRY_CAST({date_col} AS DATE) >= DATE '{date_from}'")
        if date_col and date_to:
            where.append(f"TRY_CAST({date_col} AS DATE) <= DATE '{date_to}'")
        if region_col and regions:
            listed = ", ".join("'" + r.replace("'", "''") + "'" for r in regions)
            where.append(f"CAST({region_col} AS VARCHAR) IN ({listed})")
        if id_col and customer_ids:
            listed = ", ".join("'" + i.replace("'", "''") + "'" for i in customer_ids)
            where.append(f"CAST({id_col} AS VARCHAR) IN ({listed})")
        sql = f"SELECT * FROM raw_sales WHERE {' AND '.join(where)}"
        return self.slice_sql(sql, cap=cap)


def land_paths(paths: dict[str, str]) -> DuckLanding:
    land = DuckLanding()
    for feed, path in paths.items():
        if path:
            land.attach_path(feed, path)
    if "sales" not in land.feeds:
        raise ValueError("Sales feed is required.")
    if "customers" not in land.feeds:
        raise ValueError("Customers master is required.")
    return land


def land_zip_file(zip_path: Path) -> DuckLanding:
    mapping = extract_zip(Path(zip_path))
    return land_paths({k: str(v) for k, v in mapping.items()})


def default_slice_sql(feed: str) -> str:
    view = f"raw_{feed}"
    if feed == "sales":
        return (
            f"SELECT *\nFROM {view}\n"
            "WHERE TRY_CAST(order_date AS DATE) >= DATE '2024-01-01'\n"
            "LIMIT 100000"
        )
    if feed == "customers":
        return f"SELECT *\nFROM {view}\nLIMIT 100000"
    return f"SELECT *\nFROM {view}\nLIMIT 100000"
