# src/utils/hours.py
# Business operating hours evaluation, live open/closed detection, and 12-hour time formatting.
# Connects to: src/models/store.py, src/api/routes.py
# Created: 2026-09-06

from datetime import datetime, time, timedelta
from typing import Optional
from src.models.store import DayHours, WeeklyHours

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def format_time_12hr(time_str: Optional[str]) -> str:
    """Format 24-hour HH:MM time into standard 12-hour format with AM/PM.

    Args:
        time_str: Time string e.g. '08:00' or '21:30'.

    Returns:
        Formatted string e.g. '8:00 AM' or '9:30 PM'.
    """
    if not time_str or time_str.strip() == "":
        return ""
    try:
        parts = time_str.strip().split(":")
        hours, minutes = int(parts[0]), int(parts[1])
        suffix = "AM" if hours < 12 else "PM"
        display_hour = hours % 12
        if display_hour == 0:
            display_hour = 12
        return f"{display_hour}:{minutes:02d} {suffix}"
    except (ValueError, IndexError):
        return time_str


def parse_minutes(time_str: Optional[str]) -> Optional[int]:
    """Convert HH:MM 24-hour time to minutes since midnight."""
    if not time_str:
        return None
    try:
        parts = time_str.strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        return None


def is_store_open(
    hours: WeeklyHours, reference_dt: Optional[datetime] = None
) -> tuple[bool, str, bool]:
    """Determine whether a store is currently open, along with human-readable status and closing-soon flag.

    Args:
        hours: Store's WeeklyHours schedule.
        reference_dt: Reference datetime for evaluation (defaults to datetime.now()).

    Returns:
        Tuple of (is_open: bool, status_text: str, closing_soon: bool).
    """
    dt = reference_dt or datetime.now()
    day_idx = dt.weekday()  # Monday is 0, Sunday is 6
    day_name = DAYS[day_idx]
    today_hours: DayHours = hours.get_day(day_name)

    current_minutes = dt.hour * 60 + dt.minute

    # If closed all day today
    if today_hours.is_closed or not today_hours.open_time or not today_hours.close_time:
        # Check tomorrow
        next_day_idx = (day_idx + 1) % 7
        next_hours = hours.get_day(DAYS[next_day_idx])
        if not next_hours.is_closed and next_hours.open_time:
            return False, f"Closed · Opens tomorrow at {format_time_12hr(next_hours.open_time)}", False
        return False, "Closed today", False

    open_min = parse_minutes(today_hours.open_time)
    close_min = parse_minutes(today_hours.close_time)

    if open_min is None or close_min is None:
        return False, "Hours unavailable", False

    # Handle standard daytime hours (open_min < close_min)
    if open_min < close_min:
        if current_minutes < open_min:
            return (
                False,
                f"Closed · Opens today at {format_time_12hr(today_hours.open_time)}",
                False,
            )
        elif open_min <= current_minutes < close_min:
            remaining_minutes = close_min - current_minutes
            if remaining_minutes <= 45:
                return (
                    True,
                    f"Open · Closes soon at {format_time_12hr(today_hours.close_time)} ({remaining_minutes}m left)",
                    True,
                )
            return (
                True,
                f"Open until {format_time_12hr(today_hours.close_time)}",
                False,
            )
        else:
            # Past closing time today; check tomorrow
            next_day_idx = (day_idx + 1) % 7
            next_hours = hours.get_day(DAYS[next_day_idx])
            if not next_hours.is_closed and next_hours.open_time:
                return (
                    False,
                    f"Closed · Opens tomorrow at {format_time_12hr(next_hours.open_time)}",
                    False,
                )
            return False, "Closed for the day", False

    # Handle overnight hours (e.g. 20:00 to 02:00)
    else:
        if current_minutes >= open_min or current_minutes < close_min:
            remaining = (
                (close_min - current_minutes)
                if current_minutes < close_min
                else (1440 - current_minutes + close_min)
            )
            if remaining <= 45:
                return (
                    True,
                    f"Open · Closes soon at {format_time_12hr(today_hours.close_time)} ({remaining}m left)",
                    True,
                )
            return (
                True,
                f"Open until {format_time_12hr(today_hours.close_time)}",
                False,
            )
        else:
            return (
                False,
                f"Closed · Opens today at {format_time_12hr(today_hours.open_time)}",
                False,
            )


def get_store_status_summary(
    hours: WeeklyHours, reference_dt: Optional[datetime] = None
) -> tuple[bool, str, bool]:
    """Wrapper function returning (is_open, status_text, closing_soon)."""
    return is_store_open(hours, reference_dt)
