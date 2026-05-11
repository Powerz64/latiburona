from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.backend.models import Reserva, User
from app.backend.services.auth_service import user_can_manage_global
from app.utils.constants import SERVICE_TYPES, TIME_OPTIONS
from app.utils.time_slots import hour_slots_between


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return date.today()


class AnalyticsServiceAPI:
    def __init__(self, db: Session, current_user: User) -> None:
        self.db = db
        self.current_user = current_user

    def _reservations(self, *, include_cancelled: bool = False) -> list[Reserva]:
        query = (
            select(Reserva)
            .options(joinedload(Reserva.cancha))
            .order_by(Reserva.fecha.asc(), Reserva.hora_inicio.asc())
        )
        if not include_cancelled:
            query = query.where(Reserva.estado != "cancelada")
        if not user_can_manage_global(self.current_user):
            query = query.where(Reserva.user_id == self.current_user.id)
        return list(self.db.scalars(query).all())

    def _in_range(self, reservas: list[Reserva], start: date, end: date) -> list[Reserva]:
        return [item for item in reservas if start <= _parse_date(item.fecha) <= end]

    def _hour_counts(self, reservas: list[Reserva]) -> Counter:
        counter: Counter = Counter()
        for reserva in reservas:
            for slot in hour_slots_between(reserva.hora_inicio, reserva.hora_fin):
                counter[slot] += 1
        return counter

    def _reserved_hours(self, reservas: list[Reserva]) -> int:
        return sum(len(hour_slots_between(item.hora_inicio, item.hora_fin)) for item in reservas)

    def reservations_by_day(self) -> dict:
        counts: defaultdict[str, int] = defaultdict(int)
        for reserva in self._reservations():
            counts[reserva.fecha] += 1
        return {"items": [{"date": key, "reservations": counts[key]} for key in sorted(counts)]}

    def revenue_by_day(self) -> dict:
        totals: defaultdict[str, float] = defaultdict(float)
        for reserva in self._reservations():
            totals[reserva.fecha] += float(reserva.total or 0.0)
        return {"items": [{"date": key, "revenue": round(totals[key], 2)} for key in sorted(totals)]}

    def occupancy_by_court(self) -> dict:
        reservas = self._reservations()
        unique_dates = {item.fecha for item in reservas} or {date.today().isoformat()}
        available_per_court = max(len(unique_dates) * len(TIME_OPTIONS), len(TIME_OPTIONS))
        hours_by_court: defaultdict[str, int] = defaultdict(int)
        reservations_by_court: defaultdict[str, int] = defaultdict(int)
        for reserva in reservas:
            court_name = reserva.cancha.nombre if reserva.cancha else f"Cancha {reserva.cancha_id}"
            hours_by_court[court_name] += len(hour_slots_between(reserva.hora_inicio, reserva.hora_fin))
            reservations_by_court[court_name] += 1

        items = []
        for court_name in sorted(set(SERVICE_TYPES) | set(hours_by_court)):
            occupied = hours_by_court.get(court_name, 0)
            items.append(
                {
                    "court": court_name,
                    "reservations": reservations_by_court.get(court_name, 0),
                    "occupied_slots": occupied,
                    "available_slots": available_per_court,
                    "occupancy": round((occupied / available_per_court) * 100, 2) if available_per_court else 0.0,
                }
            )
        return {"items": items}

    def peak_hours(self) -> dict:
        counter = self._hour_counts(self._reservations())
        return {
            "items": [
                {"hour": hour, "reservations": counter.get(hour, 0)}
                for hour in sorted(TIME_OPTIONS, key=lambda item: (-counter.get(item, 0), item))
            ]
        }

    def status_breakdown(self) -> dict:
        counter = Counter(item.estado for item in self._reservations(include_cancelled=True))
        return {
            "confirmed": counter.get("confirmada", 0),
            "pending": counter.get("pendiente", 0),
            "cancelled": counter.get("cancelada", 0),
            "items": [{"status": key, "reservations": counter[key]} for key in sorted(counter)],
        }

    def top_courts(self) -> dict:
        reservations = self._reservations()
        counts: Counter = Counter()
        revenue: defaultdict[str, float] = defaultdict(float)
        for reserva in reservations:
            court_name = reserva.cancha.nombre if reserva.cancha else f"Cancha {reserva.cancha_id}"
            counts[court_name] += 1
            revenue[court_name] += float(reserva.total or 0.0)
        return {
            "items": [
                {
                    "court": court,
                    "reservations": counts[court],
                    "revenue": round(revenue[court], 2),
                }
                for court, _count in counts.most_common()
            ]
        }

    def summary_for_range(self, start: date, end: date) -> dict:
        reservas = self._in_range(self._reservations(), start, end)
        status_counts = Counter(item.estado for item in reservas)
        hour_counts = self._hour_counts(reservas)
        court_counts: Counter = Counter(item.cancha.nombre if item.cancha else f"Cancha {item.cancha_id}" for item in reservas)
        top_hour = max(TIME_OPTIONS, key=lambda hour: (hour_counts.get(hour, 0), hour)) if reservas else "--"
        return {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "reservations": len(reservas),
            "confirmed": status_counts.get("confirmada", 0),
            "pending": status_counts.get("pendiente", 0),
            "revenue": round(sum(float(item.total or 0.0) for item in reservas), 2),
            "occupied_slots": self._reserved_hours(reservas),
            "peak_hour": top_hour,
            "top_court": court_counts.most_common(1)[0][0] if court_counts else "--",
        }

    def weekly_summary(self) -> dict:
        today = date.today()
        start = today - timedelta(days=today.weekday())
        return self.summary_for_range(start, start + timedelta(days=6))

    def monthly_summary(self) -> dict:
        today = date.today()
        start = today.replace(day=1)
        if today.month == 12:
            next_month = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month + 1, day=1)
        return self.summary_for_range(start, next_month - timedelta(days=1))

    def overview(self) -> dict:
        reservas = self._reservations()
        today = date.today()
        today_reservas = self._in_range(reservas, today, today)
        week = self.weekly_summary()
        status = self.status_breakdown()
        occupancy_items = self.occupancy_by_court()["items"]
        top_courts = self.top_courts()["items"]
        hour_counts = self._hour_counts(reservas)
        peak_hour = max(TIME_OPTIONS, key=lambda hour: (hour_counts.get(hour, 0), hour)) if reservas else "--"
        unique_dates = {item.fecha for item in reservas} or {today.isoformat()}
        available_slots = max(len(unique_dates) * len(SERVICE_TYPES) * len(TIME_OPTIONS), len(SERVICE_TYPES) * len(TIME_OPTIONS))
        occupied_slots = self._reserved_hours(reservas)
        return {
            "revenue": round(sum(float(item.total or 0.0) for item in reservas), 2),
            "revenue_today": round(sum(float(item.total or 0.0) for item in today_reservas), 2),
            "revenue_week": week["revenue"],
            "reservations": len(reservas),
            "confirmed_reservations": status["confirmed"],
            "pending_reservations": status["pending"],
            "occupancy": round((occupied_slots / available_slots) * 100, 2) if available_slots else 0.0,
            "top_court": top_courts[0]["court"] if top_courts else "--",
            "peak_hour": peak_hour,
            "reservations_by_hour": {hour: hour_counts.get(hour, 0) for hour in TIME_OPTIONS},
            "reservations_trend": self.reservations_by_day()["items"],
            "revenue_trend": self.revenue_by_day()["items"],
            "occupancy_by_court": occupancy_items,
            "weekly_summary": week,
            "monthly_summary": self.monthly_summary(),
            "scope": "global" if user_can_manage_global(self.current_user) else "own",
            "generated_at": datetime.utcnow().isoformat(),
        }
