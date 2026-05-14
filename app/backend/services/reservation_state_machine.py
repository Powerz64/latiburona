from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.backend.models import AuditLog, Reserva, User

DRAFT = "draft"
PENDING_PAYMENT = "pending_payment"
CONFIRMED = "confirmed"
PAID = "paid"
CANCELLED = "cancelled"
EXPIRED = "expired"
REFUNDED = "refunded"
FAILED = "failed"

LEGACY_ALIASES = {
    "": DRAFT,
    "pendiente": DRAFT,
    "confirmada": CONFIRMED,
    "cancelada": CANCELLED,
    "PENDING_PAYMENT": PENDING_PAYMENT,
    "PARTIAL_PAYMENT": PENDING_PAYMENT,
    "PAID": PAID,
    "FAILED": FAILED,
    "CANCELLED": CANCELLED,
    "EXPIRED": EXPIRED,
    "REFUNDED": REFUNDED,
}

TERMINAL_STATES = {CANCELLED, EXPIRED, REFUNDED}
ACTIVE_STATES = {DRAFT, PENDING_PAYMENT, CONFIRMED, PAID}
RELEASED_STATES = TERMINAL_STATES | {FAILED}
CONFIRMED_STATES = {CONFIRMED, PAID}
PENDING_STATES = {DRAFT, PENDING_PAYMENT}

ALLOWED_TRANSITIONS = {
    DRAFT: {DRAFT, PENDING_PAYMENT, CONFIRMED, CANCELLED, EXPIRED, FAILED},
    PENDING_PAYMENT: {PENDING_PAYMENT, PAID, CONFIRMED, CANCELLED, EXPIRED, FAILED},
    CONFIRMED: {CONFIRMED, PAID, CANCELLED, REFUNDED},
    PAID: {PAID, REFUNDED, CANCELLED},
    CANCELLED: {CANCELLED},
    EXPIRED: {EXPIRED},
    REFUNDED: {REFUNDED},
    FAILED: {FAILED, PENDING_PAYMENT, CANCELLED, EXPIRED},
}


@dataclass(slots=True)
class ReservationStateError(Exception):
    current_state: str
    target_state: str

    def __str__(self) -> str:
        return f"Transicion de reserva no permitida: {self.current_state} -> {self.target_state}"


def normalize_state(value: str | None) -> str:
    raw = str(value or "").strip()
    return LEGACY_ALIASES.get(raw, raw.lower())


def can_transition(current_state: str | None, target_state: str | None) -> bool:
    current = normalize_state(current_state)
    target = normalize_state(target_state)
    return target in ALLOWED_TRANSITIONS.get(current, set())


def apply_state_transition(
    db: Session,
    reserva: Reserva,
    target_state: str,
    *,
    actor: User | None = None,
    action: str = "reservation_state_transition",
    details: str = "",
) -> str:
    current = normalize_state(reserva.estado)
    target = normalize_state(target_state)
    if not can_transition(current, target):
        raise ReservationStateError(current, target)
    if current == target and reserva.estado == target:
        return target

    now = datetime.utcnow()
    previous = reserva.estado
    reserva.estado = target
    reserva.state_updated_at = now
    if target == CANCELLED:
        reserva.cancelled_at = reserva.cancelled_at or now
    elif target == PAID:
        reserva.paid_at = reserva.paid_at or now
    elif target == EXPIRED:
        reserva.expired_at = reserva.expired_at or now
    elif target == REFUNDED:
        reserva.refunded_at = reserva.refunded_at or now

    db.add(reserva)
    if previous != target:
        db.add(
            AuditLog(
                actor_user_id=actor.id if actor is not None else None,
                action=action,
                entity_type="reserva",
                entity_id=reserva.id,
                details=(details or f"{previous}->{target}")[:1200],
            )
        )
    return target
