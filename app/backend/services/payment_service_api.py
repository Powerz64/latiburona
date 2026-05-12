from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import parse_qs

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.backend.config import PaymentSettings, load_payment_settings
from app.backend.models import (
    AuditLog,
    PaymentTransaction,
    Reserva,
    ReservationExpiration,
    ReservationPublicLink,
    User,
)
from app.backend.services.auth_service import user_can_manage_global
from app.backend.services.reservation_service_api import (
    PENDING_RESERVATION_STATES,
    RELEASED_RESERVATION_STATES,
)

PAYMENT_STATUS_PENDING = "pending"
PAYMENT_STATUS_PAID = "paid"
PAYMENT_STATUS_FAILED = "failed"
PAYMENT_STATUS_REFUNDED = "refunded"
PAYMENT_STATUS_CANCELLED = "cancelled"

RESERVATION_PENDING_PAYMENT = "PENDING_PAYMENT"
RESERVATION_PAID = "PAID"
RESERVATION_FAILED = "FAILED"
RESERVATION_CANCELLED = "CANCELLED"
RESERVATION_REFUNDED = "REFUNDED"
RESERVATION_EXPIRED = "EXPIRED"

MERCADO_PAGO_PREFERENCES_URL = "https://api.mercadopago.com/checkout/preferences"
MERCADO_PAGO_PAYMENT_URL = "https://api.mercadopago.com/v1/payments/{payment_id}"


@dataclass
class PaymentServiceError(Exception):
    status_code: int
    message: str


def _safe_json(payload) -> str:
    try:
        return json.dumps(payload or {}, ensure_ascii=True, sort_keys=True)[:12000]
    except TypeError:
        return json.dumps({"unserializable": True}, ensure_ascii=True)


def _utcnow() -> datetime:
    return datetime.utcnow()


class MercadoPagoClient:
    def __init__(self, settings: PaymentSettings) -> None:
        self.settings = settings

    def _headers(self) -> dict[str, str]:
        if not self.settings.access_token:
            raise PaymentServiceError(503, "Mercado Pago no esta configurado para crear pagos.")
        return {
            "Authorization": f"Bearer {self.settings.access_token}",
            "Content-Type": "application/json",
        }

    def create_preference(self, payload: dict) -> dict:
        response = requests.post(
            MERCADO_PAGO_PREFERENCES_URL,
            headers=self._headers(),
            json=payload,
            timeout=12,
        )
        if response.status_code not in {200, 201}:
            raise PaymentServiceError(response.status_code, "Mercado Pago no pudo crear la preferencia.")
        return response.json()

    def get_payment(self, payment_id: str) -> dict:
        response = requests.get(
            MERCADO_PAGO_PAYMENT_URL.format(payment_id=payment_id),
            headers=self._headers(),
            timeout=12,
        )
        if response.status_code != 200:
            raise PaymentServiceError(response.status_code, "No fue posible consultar el pago en Mercado Pago.")
        return response.json()


class PaymentServiceAPI:
    def __init__(self, db: Session, current_user: User | None = None, settings: PaymentSettings | None = None) -> None:
        self.db = db
        self.current_user = current_user
        self.settings = settings or load_payment_settings()
        self.mercado_pago = MercadoPagoClient(self.settings)

    def _audit(self, action: str, reservation_id: int | None, details: str = "") -> None:
        self.db.add(
            AuditLog(
                actor_user_id=self.current_user.id if self.current_user is not None else None,
                action=action,
                entity_type="payment",
                entity_id=reservation_id,
                details=details,
            )
        )

    def _reservation_query(self, reservation_id: int):
        query = (
            select(Reserva)
            .options(joinedload(Reserva.cancha))
            .where(Reserva.id == reservation_id)
            .with_for_update()
        )
        if self.current_user is not None and not user_can_manage_global(self.current_user):
            query = query.where(Reserva.user_id == self.current_user.id)
        return query

    def get_reservation(self, reservation_id: int) -> Reserva | None:
        return self.db.scalar(self._reservation_query(reservation_id))

    def latest_transaction(self, reservation_id: int) -> PaymentTransaction | None:
        return self.db.scalar(
            select(PaymentTransaction)
            .where(PaymentTransaction.reservation_id == reservation_id)
            .order_by(PaymentTransaction.created_at.desc(), PaymentTransaction.id.desc())
        )

    def latest_expiration(self, reservation_id: int) -> ReservationExpiration | None:
        return self.db.scalar(
            select(ReservationExpiration)
            .where(ReservationExpiration.reservation_id == reservation_id)
            .order_by(ReservationExpiration.expires_at.desc(), ReservationExpiration.id.desc())
        )

    def _create_public_link(self, reservation_id: int, expires_at: datetime) -> ReservationPublicLink:
        link = ReservationPublicLink(
            reservation_id=reservation_id,
            token=secrets.token_urlsafe(32),
            expires_at=expires_at,
        )
        self.db.add(link)
        return link

    def _create_expiration(self, reservation_id: int, expires_at: datetime) -> ReservationExpiration:
        expiration = ReservationExpiration(
            reservation_id=reservation_id,
            expires_at=expires_at,
            status="pending",
        )
        self.db.add(expiration)
        return expiration

    def expire_unpaid_reservations(self) -> int:
        now = _utcnow()
        expirations = list(
            self.db.scalars(
                select(ReservationExpiration)
                .options(joinedload(ReservationExpiration.reservation))
                .where(
                    ReservationExpiration.status == "pending",
                    ReservationExpiration.expires_at <= now,
                )
            ).all()
        )
        released = 0
        for expiration in expirations:
            reserva = expiration.reservation
            if reserva and reserva.estado in PENDING_RESERVATION_STATES:
                reserva.estado = RESERVATION_EXPIRED
                self.db.add(reserva)
                released += 1
            expiration.status = "released"
            expiration.released_at = now
            self.db.add(expiration)
            self._audit("reservation_payment_expired", reserva.id if reserva else None)
        if released or expirations:
            self.db.commit()
        return released

    def _preference_payload(self, reserva: Reserva, base_url: str) -> dict:
        notification_url = f"{base_url.rstrip('/')}/payments/webhook?source_news=webhooks"
        title = f"LaTiburona - {reserva.cancha.nombre if reserva.cancha else 'Cancha'}"
        return {
            "items": [
                {
                    "title": title,
                    "description": f"{reserva.fecha} {reserva.hora_inicio}-{reserva.hora_fin}",
                    "quantity": 1,
                    "currency_id": "COP",
                    "unit_price": round(float(reserva.total or 0.0), 2),
                }
            ],
            "external_reference": str(reserva.id),
            "notification_url": notification_url,
            "metadata": {
                "reservation_id": reserva.id,
                "payment_mode": self.settings.mode,
            },
        }

    def create_payment(self, reservation_id: int, base_url: str) -> dict:
        self.expire_unpaid_reservations()
        reserva = self.get_reservation(reservation_id)
        if reserva is None:
            raise PaymentServiceError(404, "Reserva no encontrada.")
        if reserva.estado in RELEASED_RESERVATION_STATES:
            raise PaymentServiceError(409, "La reserva no esta disponible para pago.")

        existing = self.latest_transaction(reservation_id)
        expiration = self.latest_expiration(reservation_id)
        if existing and existing.status in {PAYMENT_STATUS_PENDING, PAYMENT_STATUS_PAID} and existing.payment_url:
            return self.serialize_status(reserva, existing, expiration)

        expires_at = _utcnow() + timedelta(minutes=self.settings.timeout_minutes)
        reserva.estado = RESERVATION_PENDING_PAYMENT if reserva.estado not in {"PAID", "confirmada"} else reserva.estado
        self.db.add(reserva)

        provider = self.settings.provider
        preference_id = None
        payment_url = ""
        raw_payload = {}
        if provider == "mercadopago":
            preference = self.mercado_pago.create_preference(self._preference_payload(reserva, base_url))
            preference_id = str(preference.get("id") or "")
            init_point = str(preference.get("init_point") or "")
            sandbox_init_point = str(preference.get("sandbox_init_point") or "")
            payment_url = (
                (sandbox_init_point or init_point)
                if self.settings.mode == "test"
                else (init_point or sandbox_init_point)
            )
            raw_payload = {
                "id": preference_id,
                "init_point_present": bool(preference.get("init_point")),
                "sandbox_init_point_present": bool(preference.get("sandbox_init_point")),
            }
        else:
            provider = "manual"
            preference_id = f"manual-{reservation_id}-{int(_utcnow().timestamp())}"
            payment_url = f"{base_url.rstrip('/')}/public/reservation/manual-{reservation_id}"
            raw_payload = {"provider": "manual", "mode": self.settings.mode}

        transaction = PaymentTransaction(
            reservation_id=reserva.id,
            provider=provider,
            provider_preference_id=preference_id,
            status=PAYMENT_STATUS_PENDING,
            amount=float(reserva.total or 0.0),
            currency="COP",
            payment_url=payment_url,
            raw_payload_json=_safe_json(raw_payload),
        )
        self.db.add(transaction)
        expiration = self._create_expiration(reserva.id, expires_at)
        self._audit("payment_preference_created", reserva.id, f"provider={provider}")
        self.db.commit()
        self.db.refresh(transaction)
        self.db.refresh(expiration)
        self.db.refresh(reserva)
        return self.serialize_status(reserva, transaction, expiration)

    def create_public_link(self, reservation_id: int) -> ReservationPublicLink:
        expiration = self.latest_expiration(reservation_id)
        expires_at = expiration.expires_at if expiration else _utcnow() + timedelta(minutes=self.settings.timeout_minutes)
        link = self._create_public_link(reservation_id, expires_at)
        self.db.commit()
        self.db.refresh(link)
        return link

    def serialize_status(
        self,
        reserva: Reserva,
        transaction: PaymentTransaction | None = None,
        expiration: ReservationExpiration | None = None,
    ) -> dict:
        transaction = transaction or self.latest_transaction(reserva.id)
        expiration = expiration or self.latest_expiration(reserva.id)
        return {
            "reservation_id": reserva.id,
            "reservation_status": reserva.estado,
            "payment_transaction_id": transaction.id if transaction else 0,
            "payment_status": transaction.status if transaction else PAYMENT_STATUS_PENDING,
            "status": transaction.status if transaction else PAYMENT_STATUS_PENDING,
            "amount": float(transaction.amount if transaction else reserva.total or 0.0),
            "currency": transaction.currency if transaction else "COP",
            "payment_url": transaction.payment_url if transaction else "",
            "expires_at": expiration.expires_at if expiration else None,
            "paid_at": transaction.paid_at if transaction else None,
        }

    def status_by_reservation(self, reservation_id: int) -> dict:
        self.expire_unpaid_reservations()
        reserva = self.get_reservation(reservation_id)
        if reserva is None:
            raise PaymentServiceError(404, "Reserva no encontrada.")
        return self.serialize_status(reserva)

    def _validate_webhook_signature(self, headers: dict, raw_query: str) -> bool:
        if not self.settings.webhook_secret:
            return True
        signature = str(headers.get("x-signature") or headers.get("X-Signature") or "")
        request_id = str(headers.get("x-request-id") or headers.get("X-Request-Id") or "")
        query_params = parse_qs(raw_query or "")
        data_id = (query_params.get("data.id") or query_params.get("id") or [""])[0]
        ts = ""
        received_hash = ""
        for part in signature.split(","):
            key, _, value = part.partition("=")
            if key.strip() == "ts":
                ts = value.strip()
            if key.strip() == "v1":
                received_hash = value.strip()
        manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
        expected_hash = hmac.new(
            self.settings.webhook_secret.encode(),
            msg=manifest.encode(),
            digestmod=hashlib.sha256,
        ).hexdigest()
        return bool(received_hash) and hmac.compare_digest(expected_hash, received_hash)

    def _payment_data_from_webhook(self, payload: dict, raw_query: str) -> dict:
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        query_params = parse_qs(raw_query or "")
        payment_id = str(data.get("id") or (query_params.get("data.id") or query_params.get("id") or [""])[0] or "")
        if self.settings.provider == "mercadopago" and payment_id and self.settings.access_token:
            return self.mercado_pago.get_payment(payment_id)
        return {
            "id": payment_id or payload.get("id"),
            "status": payload.get("status") or payload.get("payment_status") or "pending",
            "external_reference": payload.get("external_reference") or payload.get("reservation_id"),
            "transaction_amount": payload.get("transaction_amount") or payload.get("amount"),
            "preference_id": payload.get("preference_id"),
        }

    def process_webhook(self, payload: dict, headers: dict, raw_query: str) -> dict:
        if not self._validate_webhook_signature(headers, raw_query):
            raise PaymentServiceError(401, "Firma de webhook invalida.")

        payment_data = self._payment_data_from_webhook(payload, raw_query)
        provider_payment_id = str(payment_data.get("id") or "")
        reservation_id_raw = payment_data.get("external_reference") or payload.get("reservation_id")
        try:
            reservation_id = int(reservation_id_raw)
        except (TypeError, ValueError):
            reservation_id = 0

        transaction = None
        if provider_payment_id:
            transaction = self.db.scalar(
                select(PaymentTransaction).where(PaymentTransaction.provider_payment_id == provider_payment_id)
            )
        if transaction is None and reservation_id:
            transaction = self.latest_transaction(reservation_id)
        if transaction is None:
            raise PaymentServiceError(202, "Webhook recibido sin transaccion local asociada.")

        reserva = self.db.get(Reserva, transaction.reservation_id)
        if reserva is None:
            raise PaymentServiceError(404, "Reserva no encontrada para el pago.")

        provider_status = str(payment_data.get("status") or "").lower()
        mapped_status = self._map_provider_status(provider_status)
        previous_status = transaction.status
        transaction.provider_payment_id = provider_payment_id or transaction.provider_payment_id
        transaction.provider_preference_id = str(payment_data.get("preference_id") or transaction.provider_preference_id or "")
        transaction.status = mapped_status
        transaction.updated_at = _utcnow()
        transaction.raw_payload_json = _safe_json(
            {
                "provider_status": provider_status,
                "payment_id": provider_payment_id,
                "external_reference": reservation_id,
                "webhook_type": payload.get("type"),
                "webhook_action": payload.get("action"),
            }
        )
        if mapped_status == PAYMENT_STATUS_PAID:
            transaction.paid_at = transaction.paid_at or _utcnow()
            reserva.estado = RESERVATION_PAID
            for expiration in reserva.expirations:
                if expiration.status == "pending":
                    expiration.status = "paid"
                    self.db.add(expiration)
        elif mapped_status == PAYMENT_STATUS_FAILED:
            reserva.estado = RESERVATION_FAILED
        elif mapped_status == PAYMENT_STATUS_CANCELLED:
            reserva.estado = RESERVATION_CANCELLED
        elif mapped_status == PAYMENT_STATUS_REFUNDED:
            reserva.estado = RESERVATION_REFUNDED

        self.db.add(transaction)
        self.db.add(reserva)
        if previous_status != mapped_status:
            self._audit("payment_webhook_processed", reserva.id, f"{previous_status}->{mapped_status}")
        self.db.commit()
        return {
            "ok": True,
            "reservation_id": reserva.id,
            "payment_status": transaction.status,
            "reservation_status": reserva.estado,
        }

    @staticmethod
    def _map_provider_status(status: str) -> str:
        if status in {"approved", "accredited", "paid"}:
            return PAYMENT_STATUS_PAID
        if status in {"rejected", "failed"}:
            return PAYMENT_STATUS_FAILED
        if status in {"cancelled", "canceled"}:
            return PAYMENT_STATUS_CANCELLED
        if status in {"refunded", "charged_back"}:
            return PAYMENT_STATUS_REFUNDED
        return PAYMENT_STATUS_PENDING

    def refund(self, reservation_id: int, reason: str = "") -> dict:
        reserva = self.get_reservation(reservation_id)
        if reserva is None:
            raise PaymentServiceError(404, "Reserva no encontrada.")
        transaction = self.latest_transaction(reservation_id)
        if transaction is None:
            raise PaymentServiceError(404, "La reserva no tiene transaccion de pago.")
        self._audit("payment_refund_requested", reservation_id, reason[:300])
        return {
            "reservation_id": reservation_id,
            "payment_status": transaction.status,
            "provider": transaction.provider,
            "message": "Refund scaffold registrado; ejecutar reembolso en proveedor cuando se habilite produccion.",
        }
