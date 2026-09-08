"""Extended commercial board: filter the view, never retrain the twin."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

import pandas as pd

from src.data import AS_OF

PRESETS: tuple[str, ...] = (
    "All in twin",
    "Last month",
    "Last 3 months",
    "Last 6 months",
    "Half year",
    "Last 12 months",
    "Year to date",
    "Custom",
)

GRAINS: tuple[str, ...] = ("Day", "Week", "Month")

PLAY_LABELS: dict[str, str] = {
    "SAVE_PREMIUM": "Save",
    "LET_GO": "Let go",
    "UPSELL_LOYALTY": "Upsell",
    "NURTURE": "Nurture",
}


@dataclass(frozen=True)
class DateWindow:
    start: pd.Timestamp | None
    end: pd.Timestamp | None
    label: str


def resolve_window(
    preset: str,
    *,
    as_of: datetime | date | None = None,
    custom_from: str = "",
    custom_to: str = "",
) -> DateWindow:
    end = pd.Timestamp(as_of or AS_OF).normalize()
    name = (preset or "All in twin").strip()
    if name == "Custom":
        start = pd.to_datetime(custom_from, errors="coerce") if custom_from else pd.NaT
        stop = pd.to_datetime(custom_to, errors="coerce") if custom_to else pd.NaT
        start_ts = None if pd.isna(start) else pd.Timestamp(start).normalize()
        stop_ts = None if pd.isna(stop) else pd.Timestamp(stop).normalize()
        return DateWindow(start_ts, stop_ts, "Custom")
    if name == "All in twin":
        return DateWindow(None, None, "All in twin")
    if name == "Last month":
        start = (end - pd.DateOffset(months=1)).normalize()
    elif name == "Last 3 months":
        start = (end - pd.DateOffset(months=3)).normalize()
    elif name in ("Last 6 months", "Half year"):
        start = (end - pd.DateOffset(months=6)).normalize()
    elif name == "Last 12 months":
        start = (end - pd.DateOffset(months=12)).normalize()
    elif name == "Year to date":
        start = pd.Timestamp(year=int(end.year), month=1, day=1)
    else:
        return DateWindow(None, None, "All in twin")
    return DateWindow(start, end, name)


def _id_set(values: Iterable[str] | None) -> set[str]:
    return {str(v).strip() for v in (values or []) if str(v).strip()}


def attach_customer_attrs(sales: pd.DataFrame, customers: pd.DataFrame) -> pd.DataFrame:
    """Region/segment live on the master; receipts pick them up on customer_id."""
    out = sales.copy()
    if out.empty:
        return out
    out["customer_id"] = out["customer_id"].astype(str)
    cols = ["customer_id"]
    for col in ("region", "segment", "name"):
        if col in customers.columns:
            cols.append(col)
    master = customers[cols].copy()
    master["customer_id"] = master["customer_id"].astype(str)
    master = master.drop_duplicates("customer_id", keep="last")
    merged = out.merge(master, on="customer_id", how="left", suffixes=("", "_master"))
    for col in ("region", "segment"):
        master_col = f"{col}_master"
        if master_col in merged.columns:
            if col in merged.columns:
                merged[col] = merged[col].where(merged[col].notna() & (merged[col].astype(str) != "nan"), merged[master_col])
            else:
                merged[col] = merged[master_col]
            merged = merged.drop(columns=[master_col])
        elif col not in merged.columns:
            merged[col] = "Unknown"
    merged["region"] = merged.get("region", "Unknown").astype(str).replace({"nan": "Unknown", "None": "Unknown"})
    if "segment" in merged.columns:
        merged["segment"] = merged["segment"].astype(str).replace({"nan": "Unknown", "None": "Unknown"})
    return merged


def filter_sales(
    sales: pd.DataFrame,
    customers: pd.DataFrame,
    window: DateWindow,
    *,
    regions: list[str] | None = None,
    segments: list[str] | None = None,
    products: list[str] | None = None,
    customer_ids: list[str] | None = None,
) -> pd.DataFrame:
    out = attach_customer_attrs(sales, customers)
    if out.empty:
        return out
    out["order_date"] = pd.to_datetime(out["order_date"], errors="coerce")
    out = out.dropna(subset=["order_date"])
    if window.start is not None:
        out = out[out["order_date"] >= window.start]
    if window.end is not None:
        out = out[out["order_date"] <= window.end + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)]
    wanted_ids = _id_set(customer_ids)
    if wanted_ids:
        out = out[out["customer_id"].astype(str).isin(wanted_ids)]
    wanted_regions = _id_set(regions)
    if wanted_regions and "region" in out.columns:
        out = out[out["region"].astype(str).isin(wanted_regions)]
    wanted_segments = _id_set(segments)
    if wanted_segments and "segment" in out.columns:
        out = out[out["segment"].astype(str).isin(wanted_segments)]
    wanted_products = _id_set(products)
    if wanted_products and "product" in out.columns:
        out = out[out["product"].astype(str).isin(wanted_products)]
    return out.reset_index(drop=True)


def filter_twins(
    scored: pd.DataFrame,
    *,
    regions: list[str] | None = None,
    segments: list[str] | None = None,
    customer_ids: list[str] | None = None,
    sales_ids: Iterable[str] | None = None,
) -> pd.DataFrame:
    out = scored.copy()
    if out.empty:
        return out
    out["customer_id"] = out["customer_id"].astype(str)
    wanted_ids = _id_set(customer_ids)
    if wanted_ids:
        out = out[out["customer_id"].isin(wanted_ids)]
    elif sales_ids is not None:
        live = _id_set(sales_ids)
        if not live:
            return out.iloc[0:0].copy()
        out = out[out["customer_id"].isin(live)]
    wanted_regions = _id_set(regions)
    if wanted_regions and "region" in out.columns:
        out = out[out["region"].astype(str).isin(wanted_regions)]
    wanted_segments = _id_set(segments)
    if wanted_segments and "segment" in out.columns:
        out = out[out["segment"].astype(str).isin(wanted_segments)]
    return out.reset_index(drop=True)


def shape_metrics(sales: pd.DataFrame, customers: pd.DataFrame, twins: pd.DataFrame) -> dict[str, object]:
    dates = pd.to_datetime(sales["order_date"], errors="coerce") if not sales.empty and "order_date" in sales.columns else pd.Series(dtype="datetime64[ns]")
    dates = dates.dropna()
    return {
        "sales_rows": int(len(sales)),
        "sales_cols": int(sales.shape[1]) if not sales.empty else 0,
        "customer_rows": int(len(customers)),
        "customer_cols": int(customers.shape[1]) if not customers.empty else 0,
        "twin_rows": int(len(twins)),
        "distinct_buyers": int(sales["customer_id"].nunique()) if not sales.empty else 0,
        "revenue": float(pd.to_numeric(sales["amount"], errors="coerce").fillna(0).sum()) if not sales.empty else 0.0,
        "date_min": dates.min().date().isoformat() if len(dates) else "—",
        "date_max": dates.max().date().isoformat() if len(dates) else "—",
    }


def sales_over_time(sales: pd.DataFrame, grain: str = "Month") -> pd.DataFrame:
    if sales.empty:
        return pd.DataFrame(columns=["period", "revenue", "orders", "buyers"])
    s = sales.copy()
    s["order_date"] = pd.to_datetime(s["order_date"], errors="coerce")
    s = s.dropna(subset=["order_date"])
    g = grain if grain in GRAINS else "Month"
    if g == "Day":
        s["period"] = s["order_date"].dt.normalize()
    elif g == "Week":
        s["period"] = s["order_date"].dt.to_period("W").dt.start_time
    else:
        s["period"] = s["order_date"].dt.to_period("M").dt.to_timestamp()
    out = s.groupby("period", as_index=False).agg(
        revenue=("amount", "sum"),
        orders=("order_date", "count"),
        buyers=("customer_id", "nunique"),
    )
    return out.sort_values("period")


def sales_by_region(sales: pd.DataFrame) -> pd.DataFrame:
    if sales.empty:
        return pd.DataFrame(columns=["region", "revenue", "orders", "buyers"])
    s = sales.copy()
    if "region" not in s.columns:
        s["region"] = "Unknown"
    return (
        s.groupby("region", as_index=False)
        .agg(revenue=("amount", "sum"), orders=("order_date", "count"), buyers=("customer_id", "nunique"))
        .sort_values("revenue", ascending=False)
    )


def sales_by_product(sales: pd.DataFrame, top_n: int = 8) -> pd.DataFrame:
    if sales.empty or "product" not in sales.columns:
        return pd.DataFrame(columns=["product", "revenue", "orders"])
    out = (
        sales.groupby("product", as_index=False)
        .agg(revenue=("amount", "sum"), orders=("order_date", "count"))
        .sort_values("revenue", ascending=False)
        .head(top_n)
    )
    return out


def top_customers(sales: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    if sales.empty:
        return pd.DataFrame(columns=["customer_id", "name", "region", "revenue", "orders"])
    s = sales.copy()
    if "name" not in s.columns:
        s["name"] = s["customer_id"].astype(str)
    if "region" not in s.columns:
        s["region"] = "Unknown"
    return (
        s.groupby(["customer_id", "name", "region"], as_index=False)
        .agg(revenue=("amount", "sum"), orders=("order_date", "count"))
        .sort_values("revenue", ascending=False)
        .head(top_n)
    )


def twins_by_region(twins: pd.DataFrame) -> pd.DataFrame:
    if twins.empty or "region" not in twins.columns:
        return pd.DataFrame(columns=["region", "twins", "at_risk", "at_risk_ltv"])
    t = twins.copy()
    t["at_risk"] = t["at_risk"].astype(bool)
    ltv = pd.to_numeric(t["ltv_90_adj"], errors="coerce").fillna(0)
    t["risk_ltv"] = ltv.where(t["at_risk"], 0.0)
    return (
        t.groupby("region", as_index=False)
        .agg(twins=("customer_id", "count"), at_risk=("at_risk", "sum"), at_risk_ltv=("risk_ltv", "sum"))
        .sort_values("twins", ascending=False)
    )


def at_risk_ltv_by_region(twins: pd.DataFrame) -> pd.DataFrame:
    if twins.empty or "region" not in twins.columns:
        return pd.DataFrame(columns=["region", "at_risk_ltv", "at_risk"])
    t = twins.copy()
    t["at_risk"] = t["at_risk"].astype(bool)
    t["ltv_90_adj"] = pd.to_numeric(t["ltv_90_adj"], errors="coerce").fillna(0)
    risk = t.loc[t["at_risk"]]
    if risk.empty:
        return pd.DataFrame({"region": t["region"].unique(), "at_risk_ltv": 0.0, "at_risk": 0})
    return (
        risk.groupby("region", as_index=False)
        .agg(at_risk_ltv=("ltv_90_adj", "sum"), at_risk=("customer_id", "count"))
        .sort_values("at_risk_ltv", ascending=False)
    )


def play_mix(twins: pd.DataFrame) -> pd.DataFrame:
    if twins.empty or "action_code" not in twins.columns:
        return pd.DataFrame(columns=["play", "twins"])
    t = twins.copy()
    t["play"] = t["action_code"].map(PLAY_LABELS).fillna(t["action_code"].astype(str))
    return t.groupby("play", as_index=False).agg(twins=("customer_id", "count")).sort_values("twins", ascending=False)


def unique_values(frame: pd.DataFrame, col: str) -> list[str]:
    if frame.empty or col not in frame.columns:
        return []
    vals = (
        frame[col]
        .dropna()
        .astype(str)
        .replace({"nan": None, "None": None, "": None})
        .dropna()
        .drop_duplicates()
        .sort_values()
    )
    return [str(v) for v in vals.tolist()]
