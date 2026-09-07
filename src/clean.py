"""Eight-layer commercial clean: raw evidence stays; clean is rules we can defend."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Final

import numpy as np
import pandas as pd

from src.data import AS_OF

ALIASES: Final[dict[str, tuple[str, ...]]] = {
    "customer_id": ("customer_id", "customerid", "cust_id", "customer", "account_id", "client_id"),
    "name": ("name", "customer_name", "client_name", "account_name", "company"),
    "join_date": ("join_date", "joined", "signup_date", "start_date", "created_at"),
    "segment": ("segment", "tier", "plan_tier", "customer_segment"),
    "region": ("region", "geo", "zone", "state", "territory"),
    "total_orders": ("total_orders", "orders", "order_count", "n_orders"),
    "order_date": ("order_date", "date", "txn_date", "purchase_date", "invoice_date"),
    "amount": ("amount", "revenue", "sales", "value", "price", "total"),
    "product": ("product", "sku", "item", "plan", "catalog"),
    "quantity": ("quantity", "qty", "units", "count"),
    "last_login": ("last_login", "last_seen", "last_active", "login_at"),
    "complaints": ("complaints", "complaint_count", "n_complaints"),
    "support_tickets": ("support_tickets", "tickets", "ticket_count"),
    "days_since_last_purchase": (
        "days_since_last_purchase",
        "recency",
        "days_since_purchase",
        "recency_days",
    ),
    "email_open_rate": ("email_open_rate", "open_rate", "email_opens"),
}


@dataclass
class LayerLog:
    name: str
    detail: str
    rows_in: int
    rows_out: int


@dataclass
class FeedResult:
    name: str
    raw: pd.DataFrame
    clean: pd.DataFrame
    rejects: pd.DataFrame
    profile: dict[str, object]
    layers: list[LayerLog] = field(default_factory=list)


def _norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().lower().replace(" ", "_") for c in out.columns]
    return out


def apply_aliases(df: pd.DataFrame, needed: tuple[str, ...]) -> pd.DataFrame:
    out = _norm_cols(df)
    rename: dict[str, str] = {}
    for canonical, options in ALIASES.items():
        if canonical not in needed:
            continue
        if canonical in out.columns:
            continue
        for opt in options:
            if opt in out.columns:
                rename[opt] = canonical
                break
    return out.rename(columns=rename)


def profile_frame(df: pd.DataFrame, id_col: str = "customer_id") -> dict[str, object]:
    n = int(len(df))
    null_id = int(df[id_col].isna().sum()) if id_col in df.columns else n
    distinct = int(df[id_col].nunique()) if id_col in df.columns else 0
    return {
        "rows": n,
        "cols": int(df.shape[1]),
        "null_id": null_id,
        "distinct_id": distinct,
        "dup_id": max(n - distinct, 0) if id_col in df.columns else 0,
    }


def _parse_money(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.replace(r"[₹$,]", "", regex=True).str.replace(",", "", regex=False)
    return pd.to_numeric(text, errors="coerce")


def _parse_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def _identity(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.replace(r"\s+", "", regex=True)


def _reject(rows: pd.DataFrame, reason: str) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame(columns=list(rows.columns) + ["reject_reason"])
    out = rows.copy()
    out["reject_reason"] = reason
    return out


def clean_customers(raw: pd.DataFrame, as_of: datetime = AS_OF) -> FeedResult:
    needed = ("customer_id", "name", "join_date", "segment", "region", "total_orders")
    layers: list[LayerLog] = []
    rejects: list[pd.DataFrame] = []
    df = apply_aliases(raw, needed)
    layers.append(LayerLog("L0 land", "raw customers stored", len(raw), len(df)))
    prof = profile_frame(df)

    n0 = len(df)
    for col in needed:
        if col not in df.columns:
            df[col] = np.nan
    df["customer_id"] = _identity(df["customer_id"])
    df.loc[df["customer_id"].isin(("", "nan", "None", "NaN")), "customer_id"] = np.nan
    df["name"] = df["name"].astype(str).str.strip()
    df["join_date"] = _parse_date(df["join_date"])
    df["segment"] = df["segment"].astype(str).str.strip().replace({"nan": "Starter"})
    df["region"] = df["region"].astype(str).str.strip().replace({"nan": "Unknown"})
    df["total_orders"] = pd.to_numeric(df["total_orders"], errors="coerce")
    layers.append(LayerLog("L2 types", "IDs, dates, numerics", n0, len(df)))

    bad_id = df[df["customer_id"].isna()]
    rejects.append(_reject(bad_id, "empty customer_id"))
    df = df[df["customer_id"].notna()]
    layers.append(LayerLog("L3 identity", "drop empty IDs", n0, len(df)))

    n1 = len(df)
    df = df.sort_values("join_date", na_position="last").drop_duplicates("customer_id", keep="last")
    layers.append(LayerLog("L4 dedup", "one master row per customer_id", n1, len(df)))

    n2 = len(df)
    future = df[df["join_date"].notna() & (df["join_date"] > pd.Timestamp(as_of))]
    rejects.append(_reject(future, "join_date in the future"))
    df = df.drop(index=future.index)
    no_name = df[df["name"].isin(("", "nan"))]
    rejects.append(_reject(no_name, "missing name"))
    df = df.drop(index=no_name.index)
    layers.append(LayerLog("L5 domain", "future dates / missing names rejected", n2, len(df)))

    df["total_orders"] = df["total_orders"].fillna(0).clip(lower=0)
    df["segment"] = df["segment"].replace({"": "Starter"})
    layers.append(LayerLog("L6 complete", "defaults on optional master fields", len(df), len(df)))

    rej = pd.concat(rejects, ignore_index=True) if any(len(x) for x in rejects) else pd.DataFrame()
    return FeedResult("customers", raw, df.reset_index(drop=True), rej, prof, layers)


def clean_sales(raw: pd.DataFrame, as_of: datetime = AS_OF) -> FeedResult:
    needed = ("customer_id", "order_date", "amount", "product", "quantity")
    layers: list[LayerLog] = []
    rejects: list[pd.DataFrame] = []
    df = apply_aliases(raw, needed)
    layers.append(LayerLog("L0 land", "raw sales stored", len(raw), len(df)))
    prof = profile_frame(df)

    for col in needed:
        if col not in df.columns:
            df[col] = np.nan
    df["customer_id"] = _identity(df["customer_id"])
    df.loc[df["customer_id"].isin(("", "nan", "None")), "customer_id"] = np.nan
    df["order_date"] = _parse_date(df["order_date"])
    df["amount"] = _parse_money(df["amount"])
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["product"] = df["product"].astype(str).str.strip().replace({"nan": "Unknown", "": "Unknown"})
    layers.append(LayerLog("L2 types", "money stripped, dates parsed", len(df), len(df)))

    n0 = len(df)
    bad = df[df["customer_id"].isna() | df["order_date"].isna() | df["amount"].isna()]
    rejects.append(_reject(bad, "missing id/date/amount"))
    df = df.drop(index=bad.index)
    layers.append(LayerLog("L3 identity", "required sales keys", n0, len(df)))

    n1 = len(df)
    df = df.drop_duplicates(subset=["customer_id", "order_date", "amount", "product", "quantity"])
    layers.append(LayerLog("L4 dedup", "identical purchase rows collapsed", n1, len(df)))

    n2 = len(df)
    neg = df[(df["amount"] < 0) | (df["quantity"].fillna(1) <= 0)]
    rejects.append(_reject(neg, "amount < 0 or qty <= 0"))
    future = df[df["order_date"] > pd.Timestamp(as_of)]
    rejects.append(_reject(future, "order_date in the future"))
    df = df.drop(index=neg.index.union(future.index))
    layers.append(LayerLog("L5 domain", "impossible money/dates rejected", n2, len(df)))

    df["quantity"] = df["quantity"].fillna(1).clip(lower=1)
    layers.append(LayerLog("L6 complete", "qty default 1", len(df), len(df)))

    rej = pd.concat(rejects, ignore_index=True) if any(len(x) for x in rejects) else pd.DataFrame()
    return FeedResult("sales", raw, df.reset_index(drop=True), rej, prof, layers)


def clean_behavior(raw: pd.DataFrame, as_of: datetime = AS_OF) -> FeedResult:
    needed = (
        "customer_id",
        "last_login",
        "complaints",
        "support_tickets",
        "days_since_last_purchase",
        "email_open_rate",
    )
    layers: list[LayerLog] = []
    rejects: list[pd.DataFrame] = []
    df = apply_aliases(raw, needed)
    layers.append(LayerLog("L0 land", "raw behaviour stored", len(raw), len(df)))
    prof = profile_frame(df)
    for col in needed:
        if col not in df.columns:
            df[col] = np.nan
    df["customer_id"] = _identity(df["customer_id"])
    df.loc[df["customer_id"].isin(("", "nan", "None")), "customer_id"] = np.nan
    df["last_login"] = _parse_date(df["last_login"])
    for col in ("complaints", "support_tickets", "days_since_last_purchase"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["email_open_rate"] = pd.to_numeric(df["email_open_rate"], errors="coerce")
    layers.append(LayerLog("L2 types", "behaviour sensors numeric", len(df), len(df)))

    n0 = len(df)
    bad = df[df["customer_id"].isna()]
    rejects.append(_reject(bad, "empty customer_id"))
    df = df[df["customer_id"].notna()]
    layers.append(LayerLog("L3 identity", "drop empty IDs", n0, len(df)))

    n1 = len(df)
    df = df.sort_values("last_login", na_position="last").drop_duplicates("customer_id", keep="last")
    layers.append(LayerLog("L4 dedup", "latest snapshot per customer", n1, len(df)))

    n2 = len(df)
    df["complaints"] = df["complaints"].fillna(0).clip(lower=0)
    df["support_tickets"] = df["support_tickets"].fillna(0).clip(lower=0)
    df["days_since_last_purchase"] = df["days_since_last_purchase"].clip(lower=0)
    df["email_open_rate"] = df["email_open_rate"].clip(0, 1)
    future = df[df["last_login"].notna() & (df["last_login"] > pd.Timestamp(as_of))]
    rejects.append(_reject(future, "last_login in the future"))
    df = df.drop(index=future.index)
    layers.append(LayerLog("L5 domain", "rates clipped, future logins rejected", n2, len(df)))
    layers.append(LayerLog("L6 complete", "null sensors → 0 where counts", len(df), len(df)))

    rej = pd.concat(rejects, ignore_index=True) if any(len(x) for x in rejects) else pd.DataFrame()
    return FeedResult("behavior", raw, df.reset_index(drop=True), rej, prof, layers)


def derive_behavior_from_sales(sales_clean: pd.DataFrame, as_of: datetime = AS_OF) -> FeedResult:
    """L7 — do not invent logins. Inactivity = days since last purchase."""
    if sales_clean.empty:
        empty = pd.DataFrame(
            columns=[
                "customer_id",
                "last_login",
                "complaints",
                "support_tickets",
                "days_since_last_purchase",
                "email_open_rate",
            ]
        )
        return FeedResult(
            "behavior",
            empty,
            empty,
            pd.DataFrame(),
            {"rows": 0, "derived": True},
            [LayerLog("L7 derive", "no sales to infer from", 0, 0)],
        )
    last = sales_clean.groupby("customer_id", as_index=False).agg(last_purchase=("order_date", "max"))
    last["last_login"] = last["last_purchase"]
    last["complaints"] = 0
    last["support_tickets"] = 0
    last["days_since_last_purchase"] = (pd.Timestamp(as_of) - last["last_purchase"]).dt.days.clip(lower=0)
    last["email_open_rate"] = np.nan
    last = last.drop(columns=["last_purchase"])
    log = [
        LayerLog(
            "L7 derive",
            "behaviour inferred from sales recency — not invented logins",
            len(sales_clean),
            len(last),
        )
    ]
    return FeedResult(
        "behavior",
        last.copy(),
        last.reset_index(drop=True),
        pd.DataFrame(),
        {"rows": len(last), "derived": True},
        log,
    )
