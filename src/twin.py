"""Single Customer Twin record for the 360 + PDF."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd


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

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def twin_from_row(row: pd.Series) -> CustomerTwin:
    return CustomerTwin(
        customer_id=str(row["customer_id"]),
        name=str(row.get("name", row["customer_id"])),
        segment=str(row.get("segment", "")),
        region=str(row.get("region", "")),
        rfm_segment=str(row.get("rfm_segment", "")),
        product=str(row.get("affinity_product", "catalog")),
        recency_days=int(row["recency_days"]),
        frequency=int(row["frequency"]),
        monetary=float(row["monetary"]),
        r_score=int(row["r_score"]),
        f_score=int(row["f_score"]),
        m_score=int(row["m_score"]),
        sales_strength=float(row["sales_strength"]),
        ltv_90=float(row["ltv_90"]),
        ltv_90_adj=float(row["ltv_90_adj"]),
        next_purchase=str(row["next_purchase"]),
        p_churn=float(row["p_churn"]),
        health=float(row["health"]),
        band=str(row["band"]),
        at_risk=bool(row["at_risk"]),
        churn_reason=str(row["churn_reason"]),
        complaints=float(row["complaints"]),
        support_tickets=float(row["support_tickets"]),
        email_open_rate=float(row["email_open_rate"]),
        action_code=str(row["action_code"]),
        action_title=str(row["action_title"]),
        action_play=str(row["action_play"]),
        offer=str(row["offer"]),
    )
