from __future__ import annotations

import pandas as pd
import pytest

from src.brain import decide_row, score_book, simulate_discount
from src.data import generate_demo, join_book
from src.history import monthly_sales
from src.models import train_twin_models
from src.report import twin_pdf
from src.twin import twin_from_row


@pytest.fixture(scope="module")
def book():
    customers, sales, behavior = generate_demo(n_customers=220, seed=7)
    return join_book(customers, sales, behavior)


@pytest.fixture(scope="module")
def scored(book):
    models = train_twin_models(book.panel, seed=7)
    return models, score_book(book.panel, models)


def test_join_requires_all_three_sensors(book) -> None:
    assert len(book.panel) > 100
    assert {"customer_id", "name", "frequency", "complaints", "email_open_rate"} <= set(book.panel.columns)


def test_sales_are_transactions(book) -> None:
    assert book.sales["amount"].min() >= 0
    assert book.sales.groupby("customer_id").size().min() >= 1
    hist = monthly_sales(book.sales)
    assert len(hist) >= 10
    assert hist["revenue"].sum() > 0


def test_models_beat_chance(scored) -> None:
    models, frame = scored
    assert models.metrics["churn_auc"] >= 0.78
    assert frame["p_churn"].between(0, 1).all()
    assert (frame["ltv_90_adj"] >= 0).all()


def test_brain_matrix() -> None:
    assert decide_row(True, True)["code"] == "SAVE_PREMIUM"
    assert decide_row(False, True)["code"] == "LET_GO"
    assert decide_row(True, False)["code"] == "UPSELL_LOYALTY"
    assert decide_row(False, False)["code"] == "NURTURE"


def test_discount_lowers_mean_churn(book, scored) -> None:
    models, base = scored
    sim = simulate_discount(book.panel, models, 0.15)
    assert sim["p_churn"].mean() <= base["p_churn"].mean() + 1e-9
    assert sim["ltv_90_adj"].mean() >= base["ltv_90_adj"].mean() * 0.98


def test_pdf_and_twin_roundtrip(scored) -> None:
    _, frame = scored
    twin = twin_from_row(frame.iloc[0])
    blob = twin_pdf(twin, discount=0.1)
    assert blob.startswith(b"%PDF")
    assert twin.customer_id.startswith("CUST-")
