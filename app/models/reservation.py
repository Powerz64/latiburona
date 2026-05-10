from dataclasses import dataclass
from typing import Optional

from app.utils.time_slots import format_time_range, hours_between


@dataclass(slots=True)
class Reservation:
    id: Optional[int]
    client_name: str
    service_type: str
    reservation_date: str
    reservation_time: str
    start_time: str
    end_time: str
    people_count: int
    phone: str
    address: str
    schedule: str
    subtotal: float
    discount: float
    total: float
    status: str = "pendiente"
    created_at: Optional[str] = None

    @property
    def ticket_average(self) -> float:
        return round(self.total / self.people_count, 2) if self.people_count else 0.0

    @property
    def duration_hours(self) -> int:
        return hours_between(self.start_time, self.end_time)

    @property
    def time_range(self) -> str:
        return format_time_range(self.start_time, self.end_time)

    @property
    def cancha_id(self) -> str:
        return self.service_type
