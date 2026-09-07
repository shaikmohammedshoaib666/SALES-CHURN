"""OEE-style 3-CSV ingest: customers (master) + sales (purchase sensors) + behavior (live)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd

ROOT: Final[Path] = Path(__file__).resolve().parents[1]
DATA_DIR: Final[Path] = ROOT / "data"
AS_OF: Final[datetime] = datetime(2026, 9, 7)

CUSTOMERS_REQUIRED: Final[tuple[str, ...]] = (
    "customer_id",
    "name",
    "join_date",
    "segment",
    "region",
    "total_orders",
)
SALES_REQUIRED: Final[tuple[str, ...]] = (
    "customer_id",
    "order_date",
    "amount",
    "product",
    "quantity",
)
BEHAVIOR_REQUIRED: Final[tuple[str, ...]] = (
    "customer_id",
    "last_login",
    "complaints",
    "support_tickets",
    "days_since_last_purchase",
    "email_open_rate",
)

REGIONS: Final[tuple[str, ...]] = ("North", "South", "East", "West", "Central")
SEGMENTS: Final[tuple[str, ...]] = ("Enterprise", "Growth", "Starter")
PRODUCTS: Final[tuple[str, ...]] = (
    "Servo drive kit",
    "Conveyor bearing 6205",
    "Analytics seat",
    "Fiber 300 plan",
    "Aura bottle 1L",
    "Cold-chain logger",
    "Trade desk seat",
    "Refill pack",
)
PREFIXES: Final[tuple[str, ...]] = (
    "Helios",
    "Northwind",
    "Vanta",
    "Kodiak",
    "Nimbus",
    "Aether",
    "Sable",
    "Meridian",
    "Pinnacle",
    "Orion",
    "Lumen",
    "Atlas",
    "Harbor",
    "Zenith",
    "Quanta",
    "Solace",
    "Vertex",
    "Keel",
)
SUFFIXES: Final[tuple[str, ...]] = (
    "Works",
    "Systems",
    "Motors",
    "Foods",
    "Capital",
    "Media",
    "Energy",
    "Logistics",
    "Health",
    "Metals",
    "Labs",
    "Retail",
)


@dataclass(frozen=True, slots=True)
class TwinBook:
    customers: pd.DataFrame
    sales: pd.DataFrame
    behavior: pd.DataFrame
    panel: pd.DataFrame

    @property
    def dropped_ids(self) -> int:
        master = set(self.customers["customer_id"].astype(str))
        return len(master) - int(self.panel["customer_id"].nunique())


def _require(df: pd.DataFrame, cols: tuple[str, ...], label: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{label} missing columns: {', '.join(missing)}")


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().lower() for c in out.columns]
    return out


def load_customers(path: Path | None = None, file: object | None = None) -> pd.DataFrame:
    df = _normalize_columns(pd.read_csv(file if file is not None else path))
    _require(df, CUSTOMERS_REQUIRED, "customers.csv")
    df["customer_id"] = df["customer_id"].astype(str).str.strip()
    df["name"] = df["name"].astype(str).str.strip()
    df["join_date"] = pd.to_datetime(df["join_date"], errors="coerce")
    df["segment"] = df["segment"].astype(str)
    df["region"] = df["region"].astype(str)
    df["total_orders"] = pd.to_numeric(df["total_orders"], errors="coerce")
    df = df.dropna(subset=["customer_id", "name", "join_date"])
    return df.reset_index(drop=True)


def load_sales(path: Path | None = None, file: object | None = None) -> pd.DataFrame:
    df = _normalize_columns(pd.read_csv(file if file is not None else path))
    _require(df, SALES_REQUIRED, "sales.csv")
    df["customer_id"] = df["customer_id"].astype(str).str.strip()
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["product"] = df["product"].astype(str)
    df = df.dropna(subset=["customer_id", "order_date", "amount", "quantity"])
    df = df[(df["amount"] >= 0) & (df["quantity"] > 0)]
    return df.reset_index(drop=True)


def load_behavior(path: Path | None = None, file: object | None = None) -> pd.DataFrame:
    df = _normalize_columns(pd.read_csv(file if file is not None else path))
    _require(df, BEHAVIOR_REQUIRED, "behavior.csv")
    df["customer_id"] = df["customer_id"].astype(str).str.strip()
    df["last_login"] = pd.to_datetime(df["last_login"], errors="coerce")
    for col in ("complaints", "support_tickets", "days_since_last_purchase", "email_open_rate"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["email_open_rate"] = df["email_open_rate"].clip(0, 1)
    df = df.dropna(subset=["customer_id", "last_login"])
    return df.reset_index(drop=True)


def aggregate_sales(sales: pd.DataFrame, as_of: datetime = AS_OF) -> pd.DataFrame:
    sales = sales.copy()
    sales["order_date"] = pd.to_datetime(sales["order_date"], errors="coerce")
    agg = sales.groupby("customer_id", as_index=False).agg(
        frequency=("order_date", "count"),
        monetary=("amount", "sum"),
        avg_ticket=("amount", "mean"),
        last_purchase=("order_date", "max"),
        first_purchase=("order_date", "min"),
        units=("quantity", "sum"),
    )
    top = (
        sales.groupby(["customer_id", "product"], as_index=False)["amount"]
        .sum()
        .sort_values("amount", ascending=False)
        .drop_duplicates("customer_id")
        .rename(columns={"product": "affinity_product", "amount": "affinity_amount"})
    )
    out = agg.merge(top[["customer_id", "affinity_product"]], on="customer_id", how="left")
    last = pd.to_datetime(out["last_purchase"], errors="coerce")
    as_ts = pd.Timestamp(as_of)
    out["last_purchase"] = last
    out["recency_days"] = (as_ts - last).dt.days.clip(lower=0)
    return out


def join_book(
    customers: pd.DataFrame,
    sales: pd.DataFrame,
    behavior: pd.DataFrame,
    as_of: datetime = AS_OF,
) -> TwinBook:
    """Same join pattern as OEE Pulse: master × live sensors × purchase sensors on id."""
    sales = sales.copy()
    sales["order_date"] = pd.to_datetime(sales["order_date"], errors="coerce")
    customers = customers.copy()
    customers["join_date"] = pd.to_datetime(customers["join_date"], errors="coerce")
    behavior = behavior.copy()
    behavior["last_login"] = pd.to_datetime(behavior["last_login"], errors="coerce")
    sales_agg = aggregate_sales(sales, as_of=as_of)
    panel = customers.merge(behavior, on="customer_id", how="inner").merge(
        sales_agg, on="customer_id", how="inner"
    )
    if panel.empty:
        raise ValueError("Join produced 0 twins. customer_id must overlap in all three CSVs.")
    as_ts = pd.Timestamp(as_of)
    panel["tenure_days"] = (as_ts - panel["join_date"]).dt.days.clip(lower=1)
    panel["days_since_login"] = (as_ts - panel["last_login"]).dt.days.clip(lower=0)
    # Prefer live sensor recency when present.
    panel["recency_days"] = np.where(
        panel["days_since_last_purchase"].notna(),
        panel["days_since_last_purchase"].clip(lower=0),
        panel["recency_days"],
    )
    return TwinBook(customers=customers, sales=sales, behavior=behavior, panel=panel)


def load_demo() -> TwinBook:
    return join_book(
        load_customers(DATA_DIR / "customers.csv"),
        load_sales(DATA_DIR / "sales.csv"),
        load_behavior(DATA_DIR / "behavior.csv"),
    )


def generate_demo(n_customers: int = 360, seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    as_of = AS_OF.date()
    customers: list[dict[str, object]] = []
    sales: list[dict[str, object]] = []
    behavior: list[dict[str, object]] = []

    for i in range(n_customers):
        cid = f"CUST-{10001 + i}"
        name = f"{PREFIXES[i % len(PREFIXES)]} {SUFFIXES[(i * 5) % len(SUFFIXES)]}"
        quality = float(rng.beta(2.3, 1.5))
        price_sensitive = float(rng.random() < 0.32)
        service_friction = float(rng.random() < 0.26)
        tenure = int(rng.integers(90, 900))
        join = as_of - timedelta(days=tenure)
        segment = SEGMENTS[0 if quality > 0.72 else 1 if quality > 0.42 else 2]
        region = REGIONS[i % len(REGIONS)]

        n_orders = int(np.clip(rng.poisson(3 + quality * 9), 2, 22))
        span = max(tenure - 10, 30)
        order_days = np.sort(rng.integers(0, span, size=n_orders))
        last_order_day: int = 0
        for k, day_offset in enumerate(order_days):
            od = join + timedelta(days=int(day_offset))
            if od >= as_of:
                continue
            product = PRODUCTS[(i + k) % len(PRODUCTS)]
            qty = int(np.clip(rng.integers(1, 5), 1, 8))
            unit = float(np.exp(rng.normal(6.4 + quality * 0.7, 0.35)))
            amount = round(unit * qty, 2)
            sales.append(
                {
                    "customer_id": cid,
                    "order_date": od.isoformat(),
                    "amount": amount,
                    "product": product,
                    "quantity": qty,
                }
            )
            last_order_day = (as_of - od).days

        sold = [row for row in sales if row["customer_id"] == cid]
        if not sold:
            od = join + timedelta(days=min(21, max(tenure // 3, 5)))
            if od >= as_of:
                od = as_of - timedelta(days=9)
            sales.append(
                {
                    "customer_id": cid,
                    "order_date": od.isoformat(),
                    "amount": round(float(np.exp(rng.normal(6.2, 0.3))), 2),
                    "product": PRODUCTS[i % len(PRODUCTS)],
                    "quantity": 1,
                }
            )
            last_order_day = (as_of - od).days
        n_orders = len([row for row in sales if row["customer_id"] == cid])
        if last_order_day == 0:
            last_order_day = int(rng.integers(5, 80))

        login_lag = int(np.clip(rng.exponential(4 + (1 - quality) * 18), 0, 90))
        last_login = as_of - timedelta(days=login_lag)
        complaints = int(np.clip(rng.poisson(0.25 + price_sensitive * 1.5 + (1 - quality)), 0, 10))
        tickets = int(np.clip(rng.poisson(0.35 + service_friction * 2.0 + (1 - quality) * 1.2), 0, 14))
        open_rate = float(np.clip(rng.beta(2 + quality * 4, 2 + (1 - quality) * 3), 0.02, 0.98))

        customers.append(
            {
                "customer_id": cid,
                "name": name,
                "join_date": join.isoformat(),
                "segment": segment,
                "region": region,
                "total_orders": n_orders,
            }
        )
        behavior.append(
            {
                "customer_id": cid,
                "last_login": last_login.isoformat(),
                "complaints": complaints,
                "support_tickets": tickets,
                "days_since_last_purchase": last_order_day,
                "email_open_rate": round(open_rate, 3),
            }
        )

    return pd.DataFrame(customers), pd.DataFrame(sales), pd.DataFrame(behavior)


def write_demo(n_customers: int = 360, seed: int = 42) -> tuple[Path, Path, Path]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    customers, sales, behavior = generate_demo(n_customers=n_customers, seed=seed)
    c_path, s_path, b_path = DATA_DIR / "customers.csv", DATA_DIR / "sales.csv", DATA_DIR / "behavior.csv"
    customers.to_csv(c_path, index=False)
    sales.to_csv(s_path, index=False)
    behavior.to_csv(b_path, index=False)
    return c_path, s_path, b_path


if __name__ == "__main__":
    paths = write_demo()
    print("wrote", *paths)
