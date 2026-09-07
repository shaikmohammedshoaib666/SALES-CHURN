"""Reconstruct 12-month plant-style history from purchase sensors (OEE analog)."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from src.data import AS_OF


def monthly_sales(sales: pd.DataFrame, as_of: datetime = AS_OF, months: int = 12) -> pd.DataFrame:
    s = sales.copy()
    s["order_date"] = pd.to_datetime(s["order_date"])
    start = (as_of - pd.DateOffset(months=months)).normalize()
    s = s[s["order_date"] >= start]
    s["month"] = s["order_date"].dt.to_period("M").dt.to_timestamp()
    out = s.groupby("month", as_index=False).agg(revenue=("amount", "sum"), orders=("order_date", "count"))
    idx = pd.date_range(start=start, end=as_of, freq="MS")
    out = (
        pd.DataFrame({"month": idx})
        .merge(out, on="month", how="left")
        .fillna({"revenue": 0.0, "orders": 0})
    )
    out["ltv_cum"] = out["revenue"].cumsum()
    return out


def monthly_risk(sales: pd.DataFrame, as_of: datetime = AS_OF, months: int = 12) -> pd.DataFrame:
    """At each month-end, share of customers silent > 45 days — reconstructed hazard."""
    s = sales.copy()
    s["order_date"] = pd.to_datetime(s["order_date"])
    start = (as_of - pd.DateOffset(months=months)).normalize()
    months_idx = pd.date_range(start=start, end=as_of, freq="MS")
    rows: list[dict[str, object]] = []
    ids = s["customer_id"].unique()
    for month in months_idx:
        end = month + pd.offsets.MonthEnd(0)
        past = s[s["order_date"] <= end]
        if past.empty:
            rows.append({"month": month, "risk": 0.0, "active": 0})
            continue
        last = past.groupby("customer_id")["order_date"].max()
        recency = (end - last).dt.days
        risk = float((recency > 45).mean())
        rows.append({"month": month, "risk": risk, "active": int((recency <= 45).sum())})
    return pd.DataFrame(rows)


def customer_history(sales: pd.DataFrame, customer_id: str, as_of: datetime = AS_OF) -> pd.DataFrame:
    s = sales[sales["customer_id"].astype(str) == str(customer_id)].copy()
    if s.empty:
        return pd.DataFrame(columns=["month", "revenue", "orders", "ltv_cum"])
    return monthly_sales(s, as_of=as_of)
