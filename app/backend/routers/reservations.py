from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.db import get_db
from app.backend.models import PaymentTransaction, ReservationExpiration, User
from app.backend.schemas import ConflictResponse, ReservaCreate, ReservaOut, ReservaUpdate
from app.backend.services.auth_service import get_current_user
from app.backend.services.reservation_service_api import ReservationConflictError, ReservationServiceAPI

router = APIRouter(prefix="/reservas", tags=["reservas"])


def _latest_payment_info(db: Session, reserva_id: int) -> dict:
    payment = db.scalar(
        select(PaymentTransaction)
        .where(PaymentTransaction.reservation_id == reserva_id)
        .order_by(PaymentTransaction.created_at.desc(), PaymentTransaction.id.desc())
    )
    expiration = db.scalar(
        select(ReservationExpiration)
        .where(ReservationExpiration.reservation_id == reserva_id)
        .order_by(ReservationExpiration.expires_at.desc(), ReservationExpiration.id.desc())
    )
    return {
        "payment_status": payment.status if payment else None,
        "payment_url": payment.payment_url if payment else None,
        "payment_transaction_id": payment.id if payment else None,
        "payment_expires_at": expiration.expires_at if expiration else None,
        "state_updated_at": item.state_updated_at,
        "cancelled_at": item.cancelled_at,
        "paid_at": item.paid_at,
        "expired_at": item.expired_at,
        "refunded_at": item.refunded_at,
    }


def _serialize_reserva(item, db: Session | None = None) -> dict:
    return {
        "id": item.id,
        "user_id": item.user_id,
        "cancha_id": item.cancha_id,
        "cancha_nombre": item.cancha.nombre if item.cancha else "",
        "fecha": item.fecha,
        "hora_inicio": item.hora_inicio,
        "hora_fin": item.hora_fin,
        "estado": item.estado,
        "total": item.total,
        "subtotal": item.subtotal,
        "descuento": item.descuento,
        "jornada": item.jornada,
        "client_name": item.client_name,
        "phone": item.phone,
        "address": item.address,
        "people_count": item.people_count,
        "created_at": item.created_at,
        **(_latest_payment_info(db, item.id) if db is not None else {}),
    }


@router.get("", response_model=list[ReservaOut])
def list_reservas(
    cancha_id: int | None = Query(default=None),
    fecha: str | None = Query(default=None),
    include_cancelled: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    service = ReservationServiceAPI(db, current_user=current_user)
    items = service.list_reservas(cancha_id=cancha_id, fecha=fecha, include_cancelled=include_cancelled)
    return [_serialize_reserva(item, db) for item in items]


@router.get("/smart-suggestions")
def smart_reservation_suggestions(
    cancha_id: int = Query(...),
    fecha: str = Query(...),
    hora_inicio: str = Query(...),
    hora_fin: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    service = ReservationServiceAPI(db, current_user=current_user)
    return service.smart_suggestions(cancha_id, fecha, hora_inicio, hora_fin)


@router.get("/{reserva_id}", response_model=ReservaOut)
def get_reserva(reserva_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    service = ReservationServiceAPI(db, current_user=current_user)
    reserva = service.get_reserva(reserva_id)
    if reserva is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada")
    return _serialize_reserva(reserva, db)


@router.post(
    "",
    response_model=ReservaOut,
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_409_CONFLICT: {"model": ConflictResponse}},
)
def create_reserva(payload: ReservaCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    service = ReservationServiceAPI(db, current_user=current_user)
    try:
        reserva = service.create_reserva(payload)
    except ReservationConflictError as exc:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": exc.message, "suggestions": exc.suggestions},
        )
    return _serialize_reserva(reserva, db)


@router.put(
    "/{reserva_id}",
    response_model=ReservaOut,
    responses={status.HTTP_409_CONFLICT: {"model": ConflictResponse}},
)
def update_reserva(
    reserva_id: int,
    payload: ReservaUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ReservationServiceAPI(db, current_user=current_user)
    try:
        reserva = service.update_reserva(reserva_id, payload)
    except ReservationConflictError as exc:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": exc.message, "suggestions": exc.suggestions},
        )

    if reserva is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada")
    return _serialize_reserva(reserva, db)


@router.delete("/{reserva_id}", status_code=status.HTTP_200_OK)
def delete_reserva(
    reserva_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    service = ReservationServiceAPI(db, current_user=current_user)
    reserva = service.cancel_reserva(reserva_id)
    if reserva is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada")
    return {"message": "Reserva cancelada correctamente"}
