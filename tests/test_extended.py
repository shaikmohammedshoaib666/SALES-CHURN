from __future__ import annotations

import pandas as pd

from src.data import AS_OF, generate_demo, join_book
from src.extended import (
    attach_customer_attrs,
    filter_sales,
    filter_twins,
    resolve_window,
    sales_by_region,
    sales_over_time,
    shape_metrics,
)


def test_six_month_window_is_half_year() -> None:
    six = resolve_window("Last 6 months", as_of=AS_OF)
    half = resolve_window("Half year", as_of=AS_OF)
    assert six.start == half.start
    assert six.end == half.end
    assert six.start is not None
    assert (six.end - six.start).days >= 170


def test_region_filter_joins_from_customers() -> None:
    customers, sales, behavior = generate_demo(n_customers=80, seed=4)
    book = join_book(customers, sales, behavior)
    tagged = attach_customer_attrs(book.sales, book.customers)
    assert "region" in tagged.columns
    region = str(tagged["region"].dropna().iloc[0])
    window = resolve_window("All in twin", as_of=AS_OF)
    cut = filter_sales(book.sales, book.customers, window, regions=[region])
    assert len(cut) >= 1
    assert set(cut["region"].astype(str)) == {region}
    by_reg = sales_by_region(cut)
    assert list(by_reg["region"]) == [region]


def test_time_grain_and_shape() -> None:
    customers, sales, behavior = generate_demo(n_customers=50, seed=2)
    window = resolve_window("Last 12 months", as_of=AS_OF)
    cut = filter_sales(sales, customers, window)
    monthly = sales_over_time(cut, "Month")
    assert len(monthly) >= 1
    assert {"period", "revenue", "orders", "buyers"} <= set(monthly.columns)
    shape = shape_metrics(cut, customers, customers)
    assert shape["sales_rows"] == len(cut)
    assert shape["date_min"] != "—"


def test_filter_twins_empty_sales_window() -> None:
    scored = pd.DataFrame(
        {
            "customer_id": ["A", "B"],
            "region": ["North", "South"],
            "segment": ["Growth", "Starter"],
            "at_risk": [True, False],
            "ltv_90_adj": [10.0, 20.0],
            "action_code": ["SAVE_PREMIUM", "NURTURE"],
        }
    )
    out = filter_twins(scored, sales_ids=[])
    assert out.empty
    north = filter_twins(scored, regions=["North"])
    assert list(north["customer_id"]) == ["A"]
