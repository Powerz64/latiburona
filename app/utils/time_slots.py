from __future__ import annotations

from datetime import date, datetime, timedelta


OPERATING_START_HOUR = 6
OPERATING_END_HOUR = 23
SLOT_MINUTES = 60


def generate_time_options(start_hour: int = OPERATING_START_HOUR, end_hour: int = OPERATING_END_HOUR) -> list[str]:
    return [f"{hour:02d}:00" for hour in range(start_hour, end_hour + 1)]


def time_to_minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def minutes_to_time(value: int) -> str:
    hour = value // 60
    minute = value % 60
    return f"{hour:02d}:{minute:02d}"


def next_time_value(value: str, *, minutes: int = SLOT_MINUTES) -> str:
    return minutes_to_time(time_to_minutes(value) + minutes)


def hours_between(start_time: str, end_time: str) -> int:
    return max((time_to_minutes(end_time) - time_to_minutes(start_time)) // SLOT_MINUTES, 0)


def hour_slots_between(start_time: str, end_time: str) -> list[str]:
    start_minutes = time_to_minutes(start_time)
    end_minutes = time_to_minutes(end_time)
    return [
        minutes_to_time(value)
        for value in range(start_minutes, end_minutes, SLOT_MINUTES)
    ]


def ranges_overlap(existing_start: str, existing_end: str, new_start: str, new_end: str) -> bool:
    return existing_start < new_end and existing_end > new_start


def slot_overlap_status(slot_start: str, slot_end: str, occupied_ranges: list[dict]) -> str:
    slot_start_minutes = time_to_minutes(slot_start)
    slot_end_minutes = time_to_minutes(slot_end)
    has_partial_overlap = False

    for item in occupied_ranges:
        range_start = time_to_minutes(item["start_time"])
        range_end = time_to_minutes(item["end_time"])

        if range_start < slot_end_minutes and range_end > slot_start_minutes:
            if range_start <= slot_start_minutes and range_end >= slot_end_minutes:
                return "occupied"
            has_partial_overlap = True

    return "partial" if has_partial_overlap else "available"


def format_time_range(start_time: str, end_time: str) -> str:
    return f"{start_time} - {end_time}"


def week_dates(reference: str | date | None = None) -> list[date]:
    if isinstance(reference, str):
        current = datetime.strptime(reference, "%Y-%m-%d").date()
    elif isinstance(reference, date):
        current = reference
    else:
        current = date.today()

    monday = current - timedelta(days=current.weekday())
    return [monday + timedelta(days=offset) for offset in range(7)]
