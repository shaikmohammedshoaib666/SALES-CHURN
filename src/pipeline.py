"""Orchestrate Forge-style data plane → existing twin join (brain unchanged)."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

import pandas as pd

from src.clean import FeedResult, clean_behavior, clean_customers, clean_sales, derive_behavior_from_sales
from src.data import TwinBook, join_book

LAYER_CONTRACT = (
    "L0 land raw",
    "L1 profile",
    "L2 names & types",
    "L3 identity",
    "L4 dedup",
    "L5 domain rules",
    "L6 completeness",
    "L7 behaviour (upload or infer from sales)",
    "L8 gold join on customer_id",
)


@dataclass
class PipelineResult:
    book: TwinBook
    customers: FeedResult
    sales: FeedResult
    behavior: FeedResult
    behavior_source: str
    layer_rows: pd.DataFrame
    gold_note: str
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)


def read_tabular(file: Any) -> pd.DataFrame:
    name = str(getattr(file, "name", "upload.csv")).lower()
    if hasattr(file, "getvalue"):
        payload = file.getvalue()
        buf = BytesIO(payload)
    else:
        buf = file
    if name.endswith((".xlsx", ".xls", ".xlsm")):
        return pd.read_excel(buf)
    if name.endswith(".tsv"):
        return pd.read_csv(buf, sep="\t")
    return pd.read_csv(buf)


def _layer_table(*feeds: FeedResult) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for feed in feeds:
        for log in feed.layers:
            rows.append(
                {
                    "feed": feed.name,
                    "layer": log.name,
                    "detail": log.detail,
                    "rows_in": log.rows_in,
                    "rows_out": log.rows_out,
                }
            )
    return pd.DataFrame(rows)


def run_pipeline(
    customers_raw: pd.DataFrame,
    sales_raw: pd.DataFrame,
    behavior_raw: pd.DataFrame | None = None,
) -> PipelineResult:
    cust = clean_customers(customers_raw)
    sales = clean_sales(sales_raw)
    if behavior_raw is None or behavior_raw.empty:
        beh = derive_behavior_from_sales(sales.clean)
        source = "inferred_from_sales"
        note = "L7: no behaviour file — inactivity derived from last purchase. Logins were not invented."
    else:
        beh = clean_behavior(behavior_raw)
        source = "uploaded"
        note = "L7: behaviour file cleaned. L8 gold join on customer_id."

    if cust.clean.empty or sales.clean.empty:
        raise ValueError("Clean layer produced an empty master or sales table. Check rejects.")

    book = join_book(cust.clean, sales.clean, beh.clean)
    tables = {
        "raw_customers": cust.raw,
        "raw_sales": sales.raw,
        "raw_behavior": beh.raw,
        "clean_customers": cust.clean,
        "clean_sales": sales.clean,
        "clean_behavior": beh.clean,
        "gold_panel": book.panel,
        "rejects_customers": cust.rejects,
        "rejects_sales": sales.rejects,
        "rejects_behavior": beh.rejects,
    }
    layers = _layer_table(cust, sales, beh)
    layers = pd.concat(
        [
            layers,
            pd.DataFrame(
                [
                    {
                        "feed": "gold",
                        "layer": "L8 gold join",
                        "detail": note,
                        "rows_in": int(cust.clean["customer_id"].nunique()),
                        "rows_out": int(len(book.panel)),
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    return PipelineResult(
        book=book,
        customers=cust,
        sales=sales,
        behavior=beh,
        behavior_source=source,
        layer_rows=layers,
        gold_note=note,
        tables=tables,
    )
