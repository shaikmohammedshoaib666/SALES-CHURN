"""Human-readable twin explainers. Display only — does not change model weights."""

from __future__ import annotations

from typing import Final, Mapping

import pandas as pd

from src.features import FEATURE_COLUMNS

DEMO_CHURN_DISCLAIMER: Final[str] = (
    "Churn AUC on the demo book is a lab score. The yes/no churn labels are constructed "
    "inside this app so the model can be graded. They are not a CRM export of 'this account left'. "
    "On your own customers + sales file the AUC will change. Treat 0.89 as 'the twin can rank the demo book', not as a promise on live tenants."
)

FEATURE_LABELS: Final[Mapping[str, str]] = {
    "recency_days": "Recency days",
    "frequency": "Frequency",
    "monetary": "Monetary",
    "avg_ticket": "Avg ticket",
    "complaints": "Complaints",
    "support_tickets": "Support tickets",
    "email_open_rate": "Email open rate",
    "days_since_login": "Days since login",
    "tenure_days": "Tenure days",
    "r_score": "R score",
    "f_score": "F score",
    "m_score": "M score",
    "rfm_sum": "RFM sum",
    "sales_strength": "Sales strength",
    "health_decay": "Health decay",
    "price_pressure": "Price pressure",
    "service_pressure": "Service pressure",
    "inactivity_pressure": "Inactivity pressure",
    "cycle_days": "Cycle days",
    "monetary_90_raw": "Monetary 90 raw",
}

HEALTH_FORMULA: Final[str] = (
    "health = clip(relationship * (1 - 0.42 * churn%) + 6, 1, 99). "
    "Relationship uses recency, support tickets, complaints, email open, inactivity. "
    "RFM is the Sales Twin; this ring is relationship after a churn haircut."
)


def feature_label(name: str) -> str:
    key = str(name)
    if key in FEATURE_LABELS:
        return FEATURE_LABELS[key]
    return key.replace("_", " ").strip().capitalize() or key


def expected_value_of_action(ltv_90_adj: float, p_churn: float) -> float:
    """Same product we sort the twin list by: risk-adj LTV × churn probability."""
    ltv = max(0.0, float(ltv_90_adj))
    p = min(max(float(p_churn), 0.0), 1.0)
    return ltv * p


def ev_offer_line(*, action_title: str, ltv_90_adj: float, p_churn: float) -> str:
    ev = expected_value_of_action(ltv_90_adj, p_churn)
    verb = action_title.split(" ")[0] if action_title else "Act"
    return (
        f"{verb} ${ev:,.0f} LTV with this offer "
        f"(${ltv_90_adj:,.0f} at risk x {p_churn:.0%} churn)"
    )


def health_tooltip(
    *,
    health: float,
    recency_days: int,
    support_tickets: float,
    complaints: float,
    email_open_rate: float,
    p_churn: float,
    r_score: int,
    f_score: int,
    m_score: int,
) -> str:
    return (
        f"Health {health:.0f}/100. "
        f"RFM R{r_score} F{f_score} M{m_score}. "
        f"Recency {recency_days}d · tickets {support_tickets:.0f} · "
        f"complaints {complaints:.0f} · email open {email_open_rate:.0%} · "
        f"churn {p_churn:.0%}. {HEALTH_FORMULA}"
    )


def importance_percent_table(importances: pd.DataFrame) -> pd.DataFrame:
    """0.0443 → 4.43%. Ranking unchanged. Not a 100% pie (permutation AUC, not a budget)."""
    if importances.empty:
        return pd.DataFrame(columns=["feature", "importance_pct", "importance_label"])
    if "feature" not in importances.columns or "importance" not in importances.columns:
        raise ValueError("importance table needs feature and importance columns")
    raw = pd.to_numeric(importances["importance"], errors="coerce").fillna(0.0)
    pct = raw * 100.0
    return pd.DataFrame(
        {
            "feature": importances["feature"].map(lambda n: feature_label(str(n))),
            "importance_pct": pct.astype(float),
            "importance_label": [f"{float(v):.2f}%" for v in pct.tolist()],
        }
    )


def assert_feature_columns_labeled() -> None:
    missing = [c for c in FEATURE_COLUMNS if c not in FEATURE_LABELS]
    if missing:
        raise RuntimeError(f"FEATURE_LABELS missing {missing}")
