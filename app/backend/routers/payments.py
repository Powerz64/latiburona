from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.backend.db import get_db
from app.backend.models import User
from app.backend.schemas import (
    PaymentCreateRequest,
    PaymentCreateResponse,
    PaymentRefundRequest,
    PaymentStatusResponse,
)
from app.backend.services.auth_service import get_current_user, require_admin
from app.backend.services.payment_service_api import PaymentServiceAPI, PaymentServiceError

router = APIRouter(prefix="/payments", tags=["payments"])


def _raise_payment_error(exc: PaymentServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("/create", response_model=PaymentCreateResponse)
def create_payment(
    payload: PaymentCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    service = PaymentServiceAPI(db, current_user=current_user)
    try:
        return service.create_payment(payload.reservation_id, str(request.base_url))
    except PaymentServiceError as exc:
        _raise_payment_error(exc)


@router.post("/webhook")
async def payment_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    service = PaymentServiceAPI(db)
    try:
        return service.process_webhook(
            payload if isinstance(payload, dict) else {},
            dict(request.headers),
            request.url.query,
        )
    except PaymentServiceError as exc:
        if exc.status_code == status.HTTP_202_ACCEPTED:
            return {"ok": True, "accepted": True, "detail": exc.message}
        _raise_payment_error(exc)


@router.get("/status/{reservation_id}", response_model=PaymentStatusResponse)
def payment_status(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    service = PaymentServiceAPI(db, current_user=current_user)
    try:
        return service.status_by_reservation(reservation_id)
    except PaymentServiceError as exc:
        _raise_payment_error(exc)


@router.post("/refund")
def refund_payment(
    payload: PaymentRefundRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> dict:
    service = PaymentServiceAPI(db, current_user=_admin)
    try:
        return service.refund(payload.reservation_id, payload.reason)
    except PaymentServiceError as exc:
        _raise_payment_error(exc)
