"""Unified brain: one next-best-action from Sales Twin × Churn Twin + what-if loop."""

from __future__ import annotations

from datetime import timedelta
from typing import Final, TypedDict

import numpy as np
import pandas as pd

from src.data import AS_OF
from src.features import build_features
from src.models import TwinModels


class ActionSpec(TypedDict):
    code: str
    title: str
    play: str


ACTIONS: Final[dict[str, ActionSpec]] = {
    "save": {
        "code": "SAVE_PREMIUM",
        "title": "Save with Premium Offer",
        "play": "High-value buyer with a failing relationship. Issue a premium retain offer matched to the top driver.",
    },
    "let_go": {
        "code": "LET_GO",
        "title": "Let go / low priority",
        "play": "Low commercial value and high failure risk. Do not burn margin. Soft offboard.",
    },
    "upsell": {
        "code": "UPSELL_LOYALTY",
        "title": "Upsell / loyalty",
        "play": "Healthy high-value twin. Sell the affinity SKU or lock a loyalty term.",
    },
    "nurture": {
        "code": "NURTURE",
        "title": "Nurture",
        "play": "Low value, stable. Keep warm. No discount.",
    },
}


def decide_row(sales_high: bool, churn_high: bool) -> ActionSpec:
    if sales_high and churn_high:
        return ACTIONS["save"]
    if (not sales_high) and churn_high:
        return ACTIONS["let_go"]
    if sales_high and (not churn_high):
        return ACTIONS["upsell"]
    return ACTIONS["nurture"]


def offer_for(reason: str, action_code: str, product: str) -> str:
    if action_code == "LET_GO":
        return "No commercial offer. Free owner capacity."
    if action_code == "NURTURE":
        return "Lifecycle nurture only. Do not discount."
    if action_code == "UPSELL_LOYALTY":
        return f"Loyalty / next-cycle offer on {product}."
    mapping = {
        "Price": f"Premium retain: 10% credit on next {product} if they prepay.",
        "Service": "Named CSM + priority SLA for 60 days. No coupon.",
        "Inactivity": f"Reactivation sprint: concierge onboarding on {product}.",
    }
    return mapping.get(reason, f"Premium retain offer on {product}.")


def attach_brain(scored: pd.DataFrame) -> pd.DataFrame:
    df = scored.copy()
    if "affinity_product" not in df.columns:
        df["affinity_product"] = "catalog"
    decisions = [decide_row(bool(s), bool(c)) for s, c in zip(df["sales_high"], df["churn_high"])]
    df["action_code"] = [d["code"] for d in decisions]
    df["action_title"] = [d["title"] for d in decisions]
    df["action_play"] = [d["play"] for d in decisions]
    df["offer"] = [
        offer_for(str(r), str(a), str(p))
        for r, a, p in zip(df["churn_reason"], df["action_code"], df["affinity_product"])
    ]
    df["priority"] = df["ltv_90_adj"] * df["p_churn"]
    df["next_purchase"] = [(AS_OF + timedelta(days=int(d))).date().isoformat() for d in df["next_days"]]
    df["band"] = np.select(
        [df["p_churn"] >= 0.70, df["p_churn"] >= 0.45, df["p_churn"] >= 0.28],
        ["critical", "risk", "watch"],
        default="healthy",
    )
    return df.sort_values("priority", ascending=False).reset_index(drop=True)


def score_book(panel: pd.DataFrame, models: TwinModels) -> pd.DataFrame:
    return attach_brain(models.predict_frame(build_features(panel)))


def simulate_discount(panel: pd.DataFrame, models: TwinModels, discount: float) -> pd.DataFrame:
    """Closed-loop what-if: perturb live + purchase sensors, re-score both heads."""
    d = float(np.clip(discount, 0.0, 0.25))
    sim = panel.copy()
    sim["complaints"] = np.clip(pd.to_numeric(sim["complaints"]) * (1 - 1.35 * d), 0, None)
    sim["email_open_rate"] = np.clip(pd.to_numeric(sim["email_open_rate"]) * (1 + 0.4 * d), 0, 1)
    sim["days_since_last_purchase"] = np.clip(
        pd.to_numeric(sim["days_since_last_purchase"]) * (1 - 0.45 * d), 0, None
    )
    sim["recency_days"] = sim["days_since_last_purchase"]
    sim["avg_ticket"] = pd.to_numeric(sim["avg_ticket"]) * (1 + 0.3 * d)
    sim["monetary"] = pd.to_numeric(sim["monetary"]) * (1 + 0.12 * d)
    sim["frequency"] = np.clip(np.round(pd.to_numeric(sim["frequency"]) * (1 + 0.2 * d)), 1, None)
    return score_book(sim, models)
