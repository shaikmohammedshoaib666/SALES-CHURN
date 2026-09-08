"""Single Customer Twin record for the 360 + PDF."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from src.explain import ev_offer_line, expected_value_of_action, health_tooltip


@dataclass(frozen=True, slots=True)
class CustomerTwin:
    customer_id: str
    name: str
    segment: str
    region: str
    rfm_segment: str
    product: str
    recency_days: int
    frequency: int
    monetary: float
    r_score: int
    f_score: int
    m_score: int
    sales_strength: float
    ltv_90: float
    ltv_90_adj: float
    next_purchase: str
    p_churn: float
    health: float
    band: str
    at_risk: bool
    churn_reason: str
    complaints: float
    support_tickets: float
    email_open_rate: float
    action_code: str
    action_title: str
    action_play: str
    offer: str

    def expected_value(self) -> float:
        return expected_value_of_action(self.ltv_90_adj, self.p_churn)

    def ev_line(self) -> str:
        return ev_offer_line(
            action_title=self.action_title,
            ltv_90_adj=self.ltv_90_adj,
            p_churn=self.p_churn,
        )

    def health_why(self) -> str:
        return health_tooltip(
            health=self.health,
            recency_days=self.recency_days,
            support_tickets=self.support_tickets,
            complaints=self.complaints,
            email_open_rate=self.email_open_rate,
            p_churn=self.p_churn,
            r_score=self.r_score,
            f_score=self.f_score,
            m_score=self.m_score,
        )

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _s(row: pd.Series, key: str, default: str = "") -> str:
    if key not in row.index:
        return default
    val = row[key]
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    return str(val)


def _f(row: pd.Series, key: str, default: float = 0.0) -> float:
    if key not in row.index:
        return default
    parsed = pd.to_numeric(pd.Series([row[key]]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return default
    return float(parsed)


def _i(row: pd.Series, key: str, default: int = 0) -> int:
    return int(_f(row, key, float(default)))


def _b(row: pd.Series, key: str) -> bool:
    if key not in row.index:
        return False
    val = row[key]
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return bool(val) and not pd.isna(val)
    return bool(val)


def twin_from_row(row: pd.Series) -> CustomerTwin:
    cid = _s(row, "customer_id", "UNKNOWN")
    return CustomerTwin(
        customer_id=cid,
        name=_s(row, "name", cid),
        segment=_s(row, "segment"),
        region=_s(row, "region"),
        rfm_segment=_s(row, "rfm_segment"),
        product=_s(row, "affinity_product", "catalog"),
        recency_days=_i(row, "recency_days"),
        frequency=_i(row, "frequency", 1),
        monetary=_f(row, "monetary"),
        r_score=_i(row, "r_score", 3),
        f_score=_i(row, "f_score", 3),
        m_score=_i(row, "m_score", 3),
        sales_strength=_f(row, "sales_strength"),
        ltv_90=_f(row, "ltv_90"),
        ltv_90_adj=_f(row, "ltv_90_adj"),
        next_purchase=_s(row, "next_purchase"),
        p_churn=_f(row, "p_churn"),
        health=_f(row, "health"),
        band=_s(row, "band", "watch"),
        at_risk=_b(row, "at_risk"),
        churn_reason=_s(row, "churn_reason"),
        complaints=_f(row, "complaints"),
        support_tickets=_f(row, "support_tickets"),
        email_open_rate=_f(row, "email_open_rate"),
        action_code=_s(row, "action_code"),
        action_title=_s(row, "action_title"),
        action_play=_s(row, "action_play"),
        offer=_s(row, "offer"),
    )
