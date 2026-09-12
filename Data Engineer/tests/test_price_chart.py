from datetime import date

from price_chart import resolve_selection

BOUNDS = (date(2024, 7, 1), date(2024, 11, 27))
SESSIONS = {"filing-a": date(2024, 7, 23), "filing-b": date(2024, 7, 23)}


def test_click_resolves_exact_filing_when_several_share_a_session():
    assert resolve_selection({"kind": "filing", "filing_id": "filing-b"}, SESSIONS, BOUNDS) == (
        date(2024, 7, 23),
        date(2024, 7, 23),
        "filing-b",
    )
    assert resolve_selection({"kind": "filing", "filing_id": "missing"}, SESSIONS, BOUNDS) is None


def test_drag_preserves_empty_period_and_reverse_direction():
    assert resolve_selection(
        {"kind": "range", "start": "2024-09-13 12:00:00", "end": "2024-09-11 03:00:00"},
        SESSIONS,
        BOUNDS,
    ) == (date(2024, 9, 11), date(2024, 9, 13), None)


def test_range_clamps_to_available_prices_and_rejects_invalid_event():
    assert resolve_selection(
        {"kind": "range", "start": "2024-01-01", "end": "2025-01-01"}, SESSIONS, BOUNDS
    ) == (*BOUNDS, None)
    assert resolve_selection({"kind": "range", "start": "invalid"}, SESSIONS, BOUNDS) is None
