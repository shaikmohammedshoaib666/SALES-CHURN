from __future__ import annotations

from src.brain import score_book
from src.data import AS_OF, generate_demo, join_book
from src.models import train_twin_models
from src.queue import QUEUE_COLUMNS, build_action_queue, queue_csv_bytes, queue_filename


def test_action_queue_is_sorted_save_and_upsell() -> None:
    customers, sales, behavior = generate_demo(n_customers=80, seed=8)
    book = join_book(customers, sales, behavior)
    models = train_twin_models(book.panel, seed=8)
    scored = score_book(book.panel, models)
    queue = build_action_queue(scored, as_of=AS_OF, cut="actionable")
    assert not queue.empty
    assert set(queue["action_code"]).issubset({"SAVE_PREMIUM", "UPSELL_LOYALTY"})
    assert list(queue["expected_value"]) == sorted(queue["expected_value"], reverse=True)
    for col in QUEUE_COLUMNS:
        assert col in queue.columns
    blob = queue_csv_bytes(queue)
    assert blob.startswith(b"as_of,") or b"customer_id" in blob.splitlines()[0]
    assert "keel_action_queue_actionable_" in queue_filename(AS_OF, "actionable")
    save_only = build_action_queue(scored, as_of=AS_OF, cut="save")
    assert (save_only["action_code"] == "SAVE_PREMIUM").all()
    full = build_action_queue(scored, as_of=AS_OF, cut="all")
    assert len(full) == len(scored)
