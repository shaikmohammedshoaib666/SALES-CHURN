"""Write-back lite: action queue CSV. Does not log into Salesforce or a CRM."""

from __future__ import annotations

from datetime import datetime
from typing import Final, Literal

import pandas as pd

from src.data import AS_OF

PlayCut = Literal["actionable", "save", "all"]

ACTIONABLE_CODES: Final[frozenset[str]] = frozenset({"SAVE_PREMIUM", "UPSELL_LOYALTY"})
SAVE_CODE: Final[str] = "SAVE_PREMIUM"

QUEUE_COLUMNS: Final[tuple[str, ...]] = (
    "as_of",
    "customer_id",
    "name",
    "segment",
    "region",
    "action_code",
    "action_title",
    "offer",
    "expected_value",
    "ltv_90",
    "ltv_90_adj",
    "p_churn",
    "health",
    "churn_reason",
    "next_purchase",
    "product",
    "writeback_status",
    "loop_note",
)

LOOP_NOTE: Final[str] = (
    "Pending outside this app. Load this row into a sheet or Salesforce. "
    "Next period, join on customer_id to see if they still bought."
)


def _col_str(frame: pd.DataFrame, *keys: str) -> pd.Series:
    for key in keys:
        if key in frame.columns:
            return frame[key].astype(str)
    return pd.Series([""] * len(frame), index=frame.index)


def _col_num(frame: pd.DataFrame, key: str, default: float = 0.0) -> pd.Series:
    if key not in frame.columns:
        return pd.Series([default] * len(frame), index=frame.index, dtype=float)
    return pd.to_numeric(frame[key], errors="coerce").fillna(default)


def _codes_for_cut(cut: PlayCut) -> frozenset[str] | None:
    if cut == "all":
        return None
    if cut == "save":
        return frozenset({SAVE_CODE})
    return ACTIONABLE_CODES


def build_action_queue(
    scored: pd.DataFrame,
    *,
    as_of: datetime | None = None,
    cut: PlayCut = "actionable",
    discount: float = 0.0,
) -> pd.DataFrame:
    """One row per twin play. Sort = expected value of action (same as the dropdown)."""
    if scored.empty:
        return pd.DataFrame(columns=list(QUEUE_COLUMNS))
    frame = scored.copy()
    if "expected_value" not in frame.columns:
        if "ltv_90_adj" not in frame.columns or "p_churn" not in frame.columns:
            raise ValueError("scored twins need expected_value or ltv_90_adj and p_churn")
        frame["expected_value"] = frame["ltv_90_adj"].astype(float) * frame["p_churn"].astype(float)
    codes = _codes_for_cut(cut)
    if codes is not None:
        if "action_code" not in frame.columns:
            raise ValueError("scored twins need action_code")
        frame = frame[frame["action_code"].astype(str).isin(codes)]
    if frame.empty:
        empty = pd.DataFrame(columns=list(QUEUE_COLUMNS))
        if discount:
            empty.insert(1, "discount_sim", pd.Series(dtype=float))
        return empty
    stamp = pd.Timestamp(as_of or AS_OF).date().isoformat()
    rows = pd.DataFrame(
        {
            "as_of": stamp,
            "customer_id": frame["customer_id"].astype(str),
            "name": _col_str(frame, "name", "customer_id"),
            "segment": _col_str(frame, "segment"),
            "region": _col_str(frame, "region"),
            "action_code": frame["action_code"].astype(str),
            "action_title": _col_str(frame, "action_title"),
            "offer": _col_str(frame, "offer"),
            "expected_value": _col_num(frame, "expected_value"),
            "ltv_90": _col_num(frame, "ltv_90"),
            "ltv_90_adj": _col_num(frame, "ltv_90_adj"),
            "p_churn": _col_num(frame, "p_churn"),
            "health": _col_num(frame, "health"),
            "churn_reason": _col_str(frame, "churn_reason"),
            "next_purchase": _col_str(frame, "next_purchase"),
            "product": _col_str(frame, "affinity_product", "product"),
            "writeback_status": "pending_external",
            "loop_note": LOOP_NOTE,
        }
    )
    if discount:
        rows.insert(1, "discount_sim", float(discount))
    return rows.sort_values("expected_value", ascending=False).reset_index(drop=True)


def queue_csv_bytes(queue: pd.DataFrame) -> bytes:
    return queue.to_csv(index=False).encode("utf-8")


def queue_filename(as_of: datetime | None = None, cut: PlayCut = "actionable") -> str:
    day = pd.Timestamp(as_of or AS_OF).date().isoformat()
    return f"keel_action_queue_{cut}_{day}.csv"
