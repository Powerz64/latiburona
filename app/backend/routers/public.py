from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.db import get_db
from app.backend.models import Cancha, ReservationPublicLink
from app.backend.schemas import (
    ConflictResponse,
    PublicAvailabilityResponse,
    PublicReservationStatusResponse,
    PublicReserveRequest,
    PublicReserveResponse,
)
from app.backend.services.payment_service_api import PaymentServiceAPI, PaymentServiceError
from app.backend.services.reservation_service_api import ReservationConflictError, ReservationServiceAPI
from app.utils.constants import TIME_OPTIONS
from app.utils.time_slots import next_time_value

router = APIRouter(prefix="/public", tags=["public"])


def _raise_payment_error(exc: PaymentServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.public_detail())


@router.get("/availability", response_model=PublicAvailabilityResponse)
def public_availability(
    cancha_id: int = Query(..., ge=1),
    fecha: str = Query(..., min_length=10, max_length=10),
    db: Session = Depends(get_db),
) -> dict:
    cancha = db.get(Cancha, cancha_id)
    if cancha is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cancha no encontrada")
    service = ReservationServiceAPI(db)
    slots = []
    available_count = 0
    occupied_count = 0
    partial_count = 0

    for hora_inicio in TIME_OPTIONS:
        hora_fin = next_time_value(hora_inicio)
        available = service.is_slot_available(cancha_id, fecha, hora_inicio, hora_fin)
        slots.append(
            {
                "hora_inicio": hora_inicio,
                "hora_fin": hora_fin,
                "status": "available" if available else "occupied",
            }
        )
        if available:
            available_count += 1
        else:
            occupied_count += 1
    return {
        "cancha_id": cancha_id,
        "fecha": fecha,
        "slots": slots,
        "available_count": available_count,
        "occupied_count": occupied_count,
        "partial_count": partial_count,
    }


@router.post(
    "/reserve",
    response_model=PublicReserveResponse,
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_409_CONFLICT: {"model": ConflictResponse}},
)
def public_reserve(payload: PublicReserveRequest, request: Request, db: Session = Depends(get_db)):
    reservation_service = ReservationServiceAPI(db)
    try:
        reserva = reservation_service.create_reserva(payload)
    except ReservationConflictError as exc:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": exc.message, "suggestions": exc.suggestions},
        )

    payment_service = PaymentServiceAPI(db)
    try:
        payment = payment_service.create_payment(reserva.id, str(request.base_url))
        link = payment_service.create_public_link(reserva.id)
    except PaymentServiceError as exc:
        reserva.estado = "FAILED"
        db.add(reserva)
        db.commit()
        _raise_payment_error(exc)
    return {
        "reservation_id": reserva.id,
        "token": link.token,
        "reservation_status": payment["reservation_status"],
        "payment_status": payment["payment_status"],
        "amount": payment["amount"],
        "currency": payment["currency"],
        "payment_url": payment["payment_url"],
        "expires_at": payment["expires_at"],
    }


@router.get("/reservation/{token}", response_model=PublicReservationStatusResponse)
def public_reservation_status(token: str, db: Session = Depends(get_db)) -> dict:
    payment_service = PaymentServiceAPI(db)
    payment_service.expire_unpaid_reservations()
    link = db.scalar(select(ReservationPublicLink).where(ReservationPublicLink.token == token))
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva publica no encontrada")
    reserva = payment_service.get_reservation(link.reservation_id)
    if reserva is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada")
    status_payload = payment_service.serialize_status(reserva)
    return {
        "reservation_id": reserva.id,
        "reservation_status": reserva.estado,
        "payment_status": status_payload["payment_status"],
        "cancha_nombre": reserva.cancha.nombre if reserva.cancha else "",
        "fecha": reserva.fecha,
        "hora_inicio": reserva.hora_inicio,
        "hora_fin": reserva.hora_fin,
        "amount": status_payload["amount"],
        "currency": status_payload["currency"],
        "payment_url": status_payload["payment_url"],
        "expires_at": status_payload["expires_at"],
    }
