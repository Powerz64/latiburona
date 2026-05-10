from datetime import datetime

from .time_slots import format_time_range


def format_currency(value: float) -> str:
    return f"${value:,.0f} COP".replace(",", ".")


def format_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return value


def format_reservation_window(start_time: str, end_time: str) -> str:
    return format_time_range(start_time, end_time)
