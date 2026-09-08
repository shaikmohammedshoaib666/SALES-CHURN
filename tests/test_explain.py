from __future__ import annotations

import pandas as pd

from src.explain import (
    assert_feature_columns_labeled,
    ev_offer_line,
    expected_value_of_action,
    feature_label,
    importance_percent_table,
)
from src.features import FEATURE_COLUMNS


def test_expected_value_matches_sort_key() -> None:
    assert expected_value_of_action(17338.0, 0.53) == 17338.0 * 0.53
    line = ev_offer_line(action_title="Save with Premium Offer", ltv_90_adj=10180.0, p_churn=0.55)
    assert "Save $" in line
    assert "55%" in line
    assert "10,180" in line


def test_importance_times_100_as_percent() -> None:
    raw = pd.DataFrame(
        {
            "feature": ["support_tickets", "health_decay", "monetary_90_raw"],
            "importance": [0.0443, 0.0113, 0.0113],
        }
    )
    out = importance_percent_table(raw)
    assert out.loc[0, "importance_label"] == "4.43%"
    assert out.loc[1, "importance_label"] == "1.13%"
    assert feature_label("support_tickets") == "Support tickets"
    assert_feature_columns_labeled()
    assert set(FEATURE_COLUMNS) <= set(
        [
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
        ]
    )
