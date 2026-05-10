from __future__ import annotations

from collections import Counter
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.db import get_db
from app.backend.models import Reserva, User
from app.backend.services.auth_service import get_current_user, user_can_manage_global
from app.utils.constants import SERVICE_TYPES, TIME_OPTIONS
from app.utils.time_slots import hour_slots_between

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    query = select(Reserva).where(Reserva.estado != "cancelada").order_by(Reserva.fecha.asc(), Reserva.hora_inicio.asc())
    if not user_can_manage_global(current_user):
        query = query.where(Reserva.user_id == current_user.id)
    reservas = list(db.scalars(query).all())

    revenue = round(sum(float(item.total or 0.0) for item in reservas), 2)
    reservations = len(reservas)

    hour_counts: Counter = Counter()
    occupied_hours = 0
    unique_dates = {item.fecha for item in reservas}
    for reserva in reservas:
        slots = hour_slots_between(reserva.hora_inicio, reserva.hora_fin)
        occupied_hours += len(slots)
        for slot in slots:
            hour_counts[slot] += 1

    if not unique_dates:
        unique_dates = {date.today().isoformat()}

    available_slots = max(len(unique_dates) * len(SERVICE_TYPES) * len(TIME_OPTIONS), len(SERVICE_TYPES) * len(TIME_OPTIONS))
    occupancy = round((occupied_hours / available_slots) * 100, 2) if available_slots else 0.0

    if hour_counts:
        peak_hour = max(TIME_OPTIONS, key=lambda hour: (hour_counts.get(hour, 0), hour))
    else:
        peak_hour = "--"

    return {
        "revenue": revenue,
        "reservations": reservations,
        "occupancy": occupancy,
        "peak_hour": peak_hour,
        "scope": "global" if user_can_manage_global(current_user) else "own",
        "reservations_by_hour": {hour: hour_counts.get(hour, 0) for hour in TIME_OPTIONS},
    }
