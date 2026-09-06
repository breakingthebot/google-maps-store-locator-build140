# tests/test_hours.py
# Unit tests for operating hours calculations, open/closed evaluation, and closing soon alerts.
# Connects to: src/utils/hours.py, src/models/store.py
# Created: 2026-09-06

from datetime import datetime
from src.models.store import DayHours, WeeklyHours
from src.utils.hours import format_time_12hr, is_store_open


def test_format_time_12hr():
    """Verify 24-hour to 12-hour AM/PM formatting."""
    assert format_time_12hr("08:00") == "8:00 AM"
    assert format_time_12hr("12:00") == "12:00 PM"
    assert format_time_12hr("14:30") == "2:30 PM"
    assert format_time_12hr("21:00") == "9:00 PM"
    assert format_time_12hr("00:15") == "12:15 AM"
    assert format_time_12hr("") == ""


def test_is_store_open_during_normal_day():
    """Store with 08:00-21:00 schedule should evaluate open at 14:00."""
    hours = WeeklyHours(
        monday=DayHours(open_time="08:00", close_time="21:00", is_closed=False)
    )
    # 2026-09-07 is a Monday
    ref_dt = datetime(2026, 9, 7, 14, 0)
    is_open, status_text, closing_soon = is_store_open(hours, ref_dt)

    assert is_open is True
    assert "Open until 9:00 PM" in status_text
    assert closing_soon is False


def test_is_store_open_before_opening():
    """Store should evaluate closed before opening time."""
    hours = WeeklyHours(
        monday=DayHours(open_time="08:00", close_time="21:00", is_closed=False)
    )
    ref_dt = datetime(2026, 9, 7, 6, 30)  # 6:30 AM
    is_open, status_text, closing_soon = is_store_open(hours, ref_dt)

    assert is_open is False
    assert "Closed · Opens today at 8:00 AM" in status_text
    assert closing_soon is False


def test_is_store_open_closing_soon():
    """Store closing in 30 minutes should set closing_soon flag and notice."""
    hours = WeeklyHours(
        monday=DayHours(open_time="08:00", close_time="21:00", is_closed=False)
    )
    ref_dt = datetime(2026, 9, 7, 20, 35)  # 25 minutes left until 21:00
    is_open, status_text, closing_soon = is_store_open(hours, ref_dt)

    assert is_open is True
    assert closing_soon is True
    assert "Closes soon at 9:00 PM" in status_text
    assert "25m left" in status_text


def test_is_store_closed_after_closing():
    """Store should evaluate closed after operating hours have finished."""
    hours = WeeklyHours(
        monday=DayHours(open_time="08:00", close_time="21:00", is_closed=False),
        tuesday=DayHours(open_time="08:00", close_time="21:00", is_closed=False),
    )
    ref_dt = datetime(2026, 9, 7, 22, 15)  # 10:15 PM Monday
    is_open, status_text, closing_soon = is_store_open(hours, ref_dt)

    assert is_open is False
    assert "Closed · Opens tomorrow at 8:00 AM" in status_text


def test_is_store_closed_all_day():
    """Store marked closed all day on Sunday should evaluate as closed."""
    hours = WeeklyHours(
        sunday=DayHours(is_closed=True, open_time=None, close_time=None),
        monday=DayHours(open_time="08:00", close_time="21:00", is_closed=False),
    )
    # 2026-09-06 is a Sunday
    ref_dt = datetime(2026, 9, 6, 12, 0)
    is_open, status_text, closing_soon = is_store_open(hours, ref_dt)

    assert is_open is False
    assert "Closed · Opens tomorrow at 8:00 AM" in status_text
