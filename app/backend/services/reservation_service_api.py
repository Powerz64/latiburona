from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload

from app.backend.config import load_backend_pricing_settings
from app.backend.models import AuditLog, Cancha, Reserva, User
from app.backend.schemas import ReservaCreate, ReservaUpdate
from app.backend.services.auth_service import user_can_manage_global
from app.backend.services.reservation_state_machine import (
    CANCELLED,
    CONFIRMED,
    CONFIRMED_STATES,
    DRAFT,
    PENDING_STATES,
    RELEASED_STATES,
    ReservationStateError,
    apply_state_transition,
)
from app.services.pricing_service import PricingService
from app.utils.time_slots import generate_time_options
from app.utils.validators import ValidationError, validate_reservation_input

BUFFER_MINUTES = max(0, int(float(os.getenv("RESERVATION_TURNAROUND_MINUTES", "10") or 10)))
OPERATING_START = "08:00"
OPERATING_END = "22:00"
RELEASED_RESERVATION_STATES = {"cancelada", "CANCELLED", "FAILED", "REFUNDED", "EXPIRED", *RELEASED_STATES}
CONFIRMED_RESERVATION_STATES = {"confirmada", "PAID", *CONFIRMED_STATES}
PENDING_RESERVATION_STATES = {"pendiente", "PENDING_PAYMENT", "PARTIAL_PAYMENT", *PENDING_STATES}


@dataclass
class ReservationConflictError(Exception):
    message: str
    suggestions: list[dict[str, str]]


class BackendPricingSettingsService:
    def load_settings(self):
        return load_backend_pricing_settings()


class ReservationServiceAPI:
    def __init__(self, db: Session, current_user: User | None = None) -> None:
        self.db = db
        self.current_user = current_user
        self.pricing_service = PricingService(BackendPricingSettingsService())

    def _query(self, *, cancha_id: int | None = None, fecha: str | None = None, include_cancelled: bool = False) -> Select:
        query = select(Reserva).options(joinedload(Reserva.cancha)).order_by(Reserva.fecha.asc(), Reserva.hora_inicio.asc())
        if cancha_id is not None:
            query = query.where(Reserva.cancha_id == cancha_id)
        if fecha is not None:
            query = query.where(Reserva.fecha == fecha)
        if not include_cancelled:
            query = query.where(~Reserva.estado.in_(RELEASED_RESERVATION_STATES))
        if self.current_user is not None and not user_can_manage_global(self.current_user):
            query = query.where(Reserva.user_id == self.current_user.id)
        return query

    def _availability_query(self, *, cancha_id: int, fecha: str) -> Select:
        return (
            select(Reserva)
            .options(joinedload(Reserva.cancha))
            .where(
                Reserva.cancha_id == cancha_id,
                Reserva.fecha == fecha,
                ~Reserva.estado.in_(RELEASED_RESERVATION_STATES),
            )
            .order_by(Reserva.hora_inicio.asc())
        )

    def list_reservas(
        self,
        *,
        cancha_id: int | None = None,
        fecha: str | None = None,
        include_cancelled: bool = False,
    ) -> list[Reserva]:
        return list(self.db.scalars(self._query(cancha_id=cancha_id, fecha=fecha, include_cancelled=include_cancelled)).all())

    def get_reserva(self, reserva_id: int) -> Reserva | None:
        query = select(Reserva).options(joinedload(Reserva.cancha)).where(Reserva.id == reserva_id)
        if self.current_user is not None and not user_can_manage_global(self.current_user):
            query = query.where(Reserva.user_id == self.current_user.id)
        return self.db.scalar(query)

    def _validated_payload(self, payload: ReservaCreate | ReservaUpdate) -> dict:
        cancha = self.db.get(Cancha, payload.cancha_id)
        if cancha is None:
            raise ValidationError("La cancha seleccionada no existe.")

        return validate_reservation_input(
            {
                "client_name": payload.client_name,
                "service_type": cancha.nombre,
                "reservation_date": payload.fecha,
                "start_time": payload.hora_inicio,
                "end_time": payload.hora_fin,
                "people_count": payload.people_count,
                "phone": payload.phone,
                "address": payload.address,
                "status": payload.estado,
            }
        )

    def _audit(self, action: str, reserva: Reserva, details: str = "") -> None:
        self.db.add(
            AuditLog(
                actor_user_id=self.current_user.id if self.current_user is not None else None,
                action=action,
                entity_type="reserva",
                entity_id=reserva.id,
                details=details,
            )
        )

    def _to_datetime(self, fecha: str, hora: str) -> datetime:
        return datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")

    def _conflicts_with_buffer(
        self,
        existing: Reserva,
        *,
        fecha: str,
        hora_inicio: str,
        hora_fin: str,
    ) -> bool:
        new_start = self._to_datetime(fecha, hora_inicio)
        new_end = self._to_datetime(fecha, hora_fin)
        existing_start = self._to_datetime(existing.fecha, existing.hora_inicio) - timedelta(minutes=BUFFER_MINUTES)
        existing_end = self._to_datetime(existing.fecha, existing.hora_fin) + timedelta(minutes=BUFFER_MINUTES)
        return existing_start < new_end and existing_end > new_start

    def is_slot_available(
        self,
        cancha_id: int,
        fecha: str,
        hora_inicio: str,
        hora_fin: str,
        *,
        exclude_reserva_id: int | None = None,
    ) -> bool:
        reservas = list(self.db.scalars(self._availability_query(cancha_id=cancha_id, fecha=fecha)).all())
        for reserva in reservas:
            if exclude_reserva_id is not None and reserva.id == exclude_reserva_id:
                continue
            if self._conflicts_with_buffer(
                reserva,
                fecha=fecha,
                hora_inicio=hora_inicio,
                hora_fin=hora_fin,
            ):
                return False
        return True

    def suggest_alternatives(
        self,
        cancha_id: int,
        fecha: str,
        hora_inicio: str,
        hora_fin: str,
    ) -> list[dict[str, str]]:
        requested_start = self._to_datetime(fecha, hora_inicio)
        requested_end = self._to_datetime(fecha, hora_fin)
        duration = requested_end - requested_start
        day_start = self._to_datetime(fecha, OPERATING_START)
        day_end = self._to_datetime(fecha, OPERATING_END)

        slot_times = generate_time_options(start_hour=8, end_hour=22)
        primary_candidates: list[datetime] = []
        secondary_candidates: list[datetime] = []

        for slot_time in slot_times:
            candidate_start = self._to_datetime(fecha, slot_time)
            candidate_end = candidate_start + duration
            if candidate_end > day_end:
                continue
            if candidate_start >= requested_start:
                primary_candidates.append(candidate_start)
            else:
                secondary_candidates.append(candidate_start)

        suggestions: list[dict[str, str]] = []
        for candidate_start in primary_candidates + secondary_candidates:
            candidate_end = candidate_start + duration
            if candidate_start < day_start or candidate_end > day_end:
                continue
            if self.is_slot_available(
                cancha_id,
                fecha,
                candidate_start.strftime("%H:%M"),
                candidate_end.strftime("%H:%M"),
            ):
                suggestions.append(
                    {
                        "inicio": candidate_start.strftime("%H:%M"),
                        "fin": candidate_end.strftime("%H:%M"),
                    }
                )
            if len(suggestions) >= 3:
                break
        return suggestions

    def smart_suggestions(
        self,
        cancha_id: int,
        fecha: str,
        hora_inicio: str,
        hora_fin: str,
    ) -> dict:
        requested_start = self._to_datetime(fecha, hora_inicio)
        requested_end = self._to_datetime(fecha, hora_fin)
        duration = requested_end - requested_start
        canchas = list(self.db.scalars(select(Cancha).where(Cancha.is_active == True).order_by(Cancha.nombre.asc())).all())  # noqa: E712
        scored: list[dict] = []
        for cancha in canchas:
            reservations = list(self.db.scalars(self._availability_query(cancha_id=cancha.id, fecha=fecha)).all())
            occupied_hours = sum(
                max(0.0, (self._to_datetime(item.fecha, item.hora_fin) - self._to_datetime(item.fecha, item.hora_inicio)).total_seconds() / 3600)
                for item in reservations
            )
            available = self.is_slot_available(cancha.id, fecha, hora_inicio, hora_fin)
            utilization = min(100.0, round((occupied_hours / max(1, len(generate_time_options(start_hour=8, end_hour=22)))) * 100, 2))
            gap_penalty = 0
            if available:
                candidate_start = requested_start
                candidate_end = requested_end
                surrounding = sorted(reservations, key=lambda item: item.hora_inicio)
                for item in surrounding:
                    existing_end = self._to_datetime(item.fecha, item.hora_fin)
                    existing_start = self._to_datetime(item.fecha, item.hora_inicio)
                    if existing_end <= candidate_start:
                        gap_penalty = min(gap_penalty or 999, abs((candidate_start - existing_end).total_seconds() / 60))
                    if existing_start >= candidate_end:
                        gap_penalty = min(gap_penalty or 999, abs((existing_start - candidate_end).total_seconds() / 60))
            score = (35 if available else -80) + utilization - min(gap_penalty, 120) / 8
            scored.append(
                {
                    "cancha_id": cancha.id,
                    "court": cancha.nombre,
                    "available": available,
                    "utilization": utilization,
                    "score": round(score, 2),
                    "reason": "Mejor balance ocupacion/cupo" if available else "Horario ocupado",
                }
            )
        scored.sort(key=lambda item: (-item["score"], item["court"]))
        alternatives = self.suggest_alternatives(cancha_id, fecha, hora_inicio, hora_fin)
        return {
            "best_court": scored[0] if scored else {},
            "court_rankings": scored[:5],
            "nearby_times": alternatives,
            "buffer_minutes": BUFFER_MINUTES,
            "operational_hint": (
                "Usa la cancha sugerida para llenar huecos operativos sin crear traslapes."
                if scored and scored[0].get("available")
                else "El rango solicitado esta congestionado; revisa horarios cercanos."
            ),
        }

    def create_reserva(self, payload: ReservaCreate) -> Reserva:
        cleaned = self._validated_payload(payload)
        if not self.is_slot_available(
            payload.cancha_id,
            cleaned["reservation_date"],
            cleaned["start_time"],
            cleaned["end_time"],
        ):
            raise ReservationConflictError(
                "Horario no disponible",
                self.suggest_alternatives(
                    payload.cancha_id,
                    cleaned["reservation_date"],
                    cleaned["start_time"],
                    cleaned["end_time"],
                ),
            )

        pricing = self.pricing_service.calculate_price(
            cleaned["reservation_date"],
            cleaned["start_time"],
            cleaned["people_count"],
            cleaned["end_time"],
        )
        reserva = Reserva(
            user_id=self.current_user.id if self.current_user is not None else None,
            cancha_id=payload.cancha_id,
            fecha=cleaned["reservation_date"],
            hora_inicio=cleaned["start_time"],
            hora_fin=cleaned["end_time"],
            estado=DRAFT,
            total=pricing.total,
            subtotal=pricing.subtotal,
            descuento=pricing.discount,
            jornada=pricing.schedule,
            client_name=cleaned["client_name"],
            phone=cleaned["phone"],
            address=cleaned["address"],
            people_count=cleaned["people_count"],
        )
        self.db.add(reserva)
        self.db.flush()
        apply_state_transition(
            self.db,
            reserva,
            cleaned["status"] or DRAFT,
            actor=self.current_user,
            action="reservation_created",
            details=f"{reserva.fecha} {reserva.hora_inicio}-{reserva.hora_fin}",
        )
        self._audit("reservation_created", reserva, f"{reserva.fecha} {reserva.hora_inicio}-{reserva.hora_fin}")
        self.db.commit()
        self.db.refresh(reserva)
        return self.get_reserva(reserva.id) or reserva

    def update_reserva(self, reserva_id: int, payload: ReservaUpdate) -> Reserva | None:
        reserva = self.get_reserva(reserva_id)
        if reserva is None:
            return None

        cleaned = self._validated_payload(payload)
        if not self.is_slot_available(
            payload.cancha_id,
            cleaned["reservation_date"],
            cleaned["start_time"],
            cleaned["end_time"],
            exclude_reserva_id=reserva_id,
        ):
            raise ReservationConflictError(
                "Horario no disponible",
                self.suggest_alternatives(
                    payload.cancha_id,
                    cleaned["reservation_date"],
                    cleaned["start_time"],
                    cleaned["end_time"],
                ),
            )

        pricing = self.pricing_service.calculate_price(
            cleaned["reservation_date"],
            cleaned["start_time"],
            cleaned["people_count"],
            cleaned["end_time"],
        )
        reserva.cancha_id = payload.cancha_id
        if self.current_user is not None and reserva.user_id is None:
            reserva.user_id = self.current_user.id
        reserva.fecha = cleaned["reservation_date"]
        reserva.hora_inicio = cleaned["start_time"]
        reserva.hora_fin = cleaned["end_time"]
        try:
            apply_state_transition(
                self.db,
                reserva,
                cleaned["status"],
                actor=self.current_user,
                action="reservation_updated",
                details=f"estado={cleaned['status']}",
            )
        except ReservationStateError as exc:
            raise ValidationError(str(exc)) from exc
        reserva.total = pricing.total
        reserva.subtotal = pricing.subtotal
        reserva.descuento = pricing.discount
        reserva.jornada = pricing.schedule
        reserva.client_name = cleaned["client_name"]
        reserva.phone = cleaned["phone"]
        reserva.address = cleaned["address"]
        reserva.people_count = cleaned["people_count"]

        self.db.add(reserva)
        self._audit("reservation_updated", reserva, f"estado={reserva.estado}")
        self.db.commit()
        self.db.refresh(reserva)
        return self.get_reserva(reserva.id) or reserva

    def cancel_reserva(self, reserva_id: int) -> Reserva | None:
        reserva = self.get_reserva(reserva_id)
        if reserva is None:
            return None
        apply_state_transition(
            self.db,
            reserva,
            CANCELLED,
            actor=self.current_user,
            action="reservation_cancelled",
        )
        self.db.add(reserva)
        self._audit("reservation_cancelled", reserva)
        self.db.commit()
        self.db.refresh(reserva)
        return self.get_reserva(reserva.id) or reserva
