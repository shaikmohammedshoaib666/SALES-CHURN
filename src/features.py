"""RFM from purchase sensors + behavioral decay from live sensors. Shared as-of clock."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from src.data import AS_OF


def rfm_quintile(series: pd.Series, *, reverse: bool = False) -> pd.Series:
    ranked = series.rank(method="first")
    if reverse:
        ranked = -ranked
    try:
        return pd.qcut(ranked, 5, labels=[1, 2, 3, 4, 5], duplicates="drop").astype(int)
    except ValueError:
        return pd.Series(np.full(len(series), 3, dtype=int), index=series.index)


def build_features(panel: pd.DataFrame, as_of: datetime | None = None) -> pd.DataFrame:
    as_of = as_of or AS_OF
    df = panel.copy()
    df["frequency"] = pd.to_numeric(df["frequency"], errors="coerce").fillna(1).clip(lower=1)
    df["monetary"] = pd.to_numeric(df["monetary"], errors="coerce").fillna(0).clip(lower=0)
    df["avg_ticket"] = pd.to_numeric(df["avg_ticket"], errors="coerce").fillna(df["monetary"] / df["frequency"])
    df["recency_days"] = pd.to_numeric(df["recency_days"], errors="coerce").fillna(30).clip(lower=0)
    df["complaints"] = pd.to_numeric(df["complaints"], errors="coerce").fillna(0).clip(lower=0)
    df["support_tickets"] = pd.to_numeric(df["support_tickets"], errors="coerce").fillna(0).clip(lower=0)
    df["email_open_rate"] = pd.to_numeric(df["email_open_rate"], errors="coerce").fillna(0.2).clip(0, 1)
    df["days_since_login"] = pd.to_numeric(df.get("days_since_login", df["recency_days"]), errors="coerce").fillna(7)
    df["tenure_days"] = pd.to_numeric(df.get("tenure_days", 180), errors="coerce").fillna(180).clip(lower=1)

    df["cycle_days"] = np.clip((df["recency_days"] + 14) / df["frequency"] * 4, 7, 180)
    df["r_score"] = rfm_quintile(df["recency_days"], reverse=True)
    df["f_score"] = rfm_quintile(df["frequency"], reverse=False)
    df["m_score"] = rfm_quintile(df["monetary"], reverse=False)
    df["rfm_sum"] = df["r_score"] + df["f_score"] + df["m_score"]
    df["sales_strength"] = df["rfm_sum"] / 15.0

    inactivity = df["recency_days"] / 30.0
    login_gap = df["days_since_login"] / 21.0
    decay = (
        np.exp(-0.32 * inactivity)
        * np.exp(-0.22 * login_gap)
        * np.exp(-0.10 * df["support_tickets"])
        * np.exp(-0.14 * df["complaints"])
    )
    engagement = 0.6 * df["email_open_rate"] + 0.4 * np.clip(1 - login_gap / 3, 0, 1)
    df["health_decay"] = np.clip(100 * (0.62 * decay + 0.38 * engagement), 1.0, 99.0)

    df["price_pressure"] = np.clip(df["complaints"] / (1 + df["frequency"] / 4), 0, 5)
    df["service_pressure"] = np.clip(df["support_tickets"] / 6.0, 0, 4)
    df["inactivity_pressure"] = np.clip(
        0.6 * (df["recency_days"] / 90.0) + 0.4 * ((1 - df["email_open_rate"]) * 2),
        0,
        4,
    )
    reason_mat = np.vstack(
        [
            df["price_pressure"].to_numpy(),
            df["service_pressure"].to_numpy(),
            df["inactivity_pressure"].to_numpy(),
        ]
    )
    df["churn_reason"] = np.array(["Price", "Service", "Inactivity"])[reason_mat.argmax(axis=0)]
    df["monetary_90_raw"] = df["avg_ticket"] * (90.0 / df["cycle_days"])
    df["rfm_segment"] = np.select(
        [df["rfm_sum"] >= 12, df["rfm_sum"] >= 9, df["rfm_sum"] >= 6],
        ["Champion", "Loyal", "Need attention"],
        default="At risk value",
    )
    return df


FEATURE_COLUMNS: tuple[str, ...] = (
    "recency_days",
    "frequency",
    "monetary",
    "avg_ticket",
    "complaints",
    "support_tickets",
    "email_open_rate",
    "days_since_login",
    "tenure_days",
    "r_score",
    "f_score",
    "m_score",
    "rfm_sum",
    "sales_strength",
    "health_decay",
    "price_pressure",
    "service_pressure",
    "inactivity_pressure",
    "cycle_days",
    "monetary_90_raw",
)


def model_matrix(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[:, list(FEATURE_COLUMNS)].astype(float)
