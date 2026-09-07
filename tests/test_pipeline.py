from __future__ import annotations

import pandas as pd
import pytest

from src.brain import decide_row, score_book, simulate_discount
from src.data import generate_demo, join_book
from src.history import monthly_sales
from src.models import train_twin_models
from src.report import twin_pdf
from src.twin import twin_from_row
from src.pipeline import run_pipeline
from src.warehouse import run_sql


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
    assert models.metrics["churn_auc"] >= 0.82
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


def test_messy_sales_and_alias_columns_clean() -> None:
    customers = pd.DataFrame(
        {
            "Customer ID": [" a1 ", "a1", "b2", ""],
            "Customer Name": ["Acme", "Acme Dup", "Beta", "NoId"],
            "Join Date": ["2024-01-01", "2024-06-01", "2024-02-02", "2024-01-01"],
            "Segment": ["Growth", "Growth", "Starter", "Starter"],
            "Region": ["North", "North", "South", "East"],
            "Total Orders": [3, 4, 1, 1],
        }
    )
    sales = pd.DataFrame(
        {
            "cust_id": ["a1", "a1", "a1", "b2", "b2"],
            "order_date": ["2024-03-01", "2024-03-01", "2024-08-01", "2024-04-01", "2099-01-01"],
            "amount": ["₹1,200", "₹1,200", "800", "-50", "100"],
            "product": ["Seat", "Seat", "Kit", "Kit", "Kit"],
            "qty": [1, 1, 2, 1, 1],
        }
    )
    pipe = run_pipeline(customers, sales, None)
    assert pipe.behavior_source == "inferred_from_sales"
    assert "a1" in set(pipe.customers.clean["customer_id"])
    assert pipe.customers.clean["customer_id"].nunique() == 2
    assert (pipe.sales.clean["amount"] >= 0).all()
    assert len(pipe.sales.rejects) >= 1
    assert len(pipe.book.panel) >= 1


def test_duckdb_sql_lab_on_clean_sales() -> None:
    customers, sales, behavior = generate_demo(n_customers=40, seed=3)
    pipe = run_pipeline(customers, sales, behavior)
    out, engine = run_sql(
        "SELECT COUNT(*) AS n FROM clean_sales",
        pipe.tables,
    )
    assert engine == "duckdb"
    assert int(out["n"].iloc[0]) == len(pipe.sales.clean)


def test_write_sql_is_blocked() -> None:
    customers, sales, behavior = generate_demo(n_customers=20, seed=1)
    pipe = run_pipeline(customers, sales, behavior)
    with pytest.raises(ValueError, match="read-only"):
        run_sql("DROP TABLE clean_sales", pipe.tables)

