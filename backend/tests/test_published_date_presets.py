from datetime import date

from app.agent.published_date_presets import (
    PRESET_CUSTOM,
    PRESET_LAST_7_DAYS,
    PRESET_THIS_WEEK,
    PRESET_THIS_YEAR,
    resolve_published_date_range,
)


def test_resolve_all_returns_no_filter():
    assert resolve_published_date_range(None, date(2025, 1, 1), date(2025, 12, 31)) == (None, None)
    assert resolve_published_date_range("all", date(2025, 1, 1), date(2025, 12, 31)) == (None, None)


def test_resolve_custom_uses_stored_dates():
    start = date(2025, 3, 1)
    end = date(2025, 3, 31)
    assert resolve_published_date_range(PRESET_CUSTOM, start, end) == (start, end)


def test_resolve_this_week_from_monday():
    ref = date(2026, 6, 25)  # Thursday
    start, end = resolve_published_date_range(PRESET_THIS_WEEK, None, None, reference=ref)
    assert start == date(2026, 6, 22)
    assert end == ref


def test_resolve_last_7_days_inclusive():
    ref = date(2026, 6, 25)
    start, end = resolve_published_date_range(PRESET_LAST_7_DAYS, None, None, reference=ref)
    assert start == date(2026, 6, 19)
    assert end == ref


def test_resolve_this_year():
    ref = date(2026, 6, 25)
    start, end = resolve_published_date_range(PRESET_THIS_YEAR, None, None, reference=ref)
    assert start == date(2026, 1, 1)
    assert end == ref
