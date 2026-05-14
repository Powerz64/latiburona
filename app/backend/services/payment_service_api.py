from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlencode

import requests
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.backend.config import PaymentSettings, load_payment_settings
from app.backend.models import (
    AuditLog,
    PaymentEvent,
    PaymentTransaction,
    Reserva,
    ReservationExpiration,
    ReservationPublicLink,
    User,
    WebhookDeliveryLog,
)
from app.backend.services.auth_service import user_can_manage_global
from app.backend.services.reservation_service_api import (
    PENDING_RESERVATION_STATES,
    RELEASED_RESERVATION_STATES,
)
from app.backend.services.reservation_state_machine import (
    apply_state_transition,
    CANCELLED as RESERVATION_CANCELLED,
    EXPIRED as RESERVATION_EXPIRED,
    FAILED as RESERVATION_FAILED,
    PAID as RESERVATION_PAID,
    PENDING_PAYMENT as RESERVATION_PENDING_PAYMENT,
    REFUNDED as RESERVATION_REFUNDED,
    ReservationStateError,
)

PAYMENT_STATUS_PENDING = "pending"
PAYMENT_STATUS_PAID = "paid"
PAYMENT_STATUS_FAILED = "failed"
PAYMENT_STATUS_REFUNDED = "refunded"
PAYMENT_STATUS_CANCELLED = "cancelled"

MERCADO_PAGO_PREFERENCES_URL = "https://api.mercadopago.com/checkout/preferences"
MERCADO_PAGO_PAYMENT_URL = "https://api.mercadopago.com/v1/payments/{payment_id}"
logger = logging.getLogger("latiburona.payments")


@dataclass
class PaymentServiceError(Exception):
    status_code: int
    message: str
    code: str = "payment_error"

    def __str__(self) -> str:
        return self.message

    def public_detail(self) -> dict:
        return {
            "error": self.code,
            "message": self.message,
            "retryable": self.status_code >= 500,
        }


def _safe_json(payload) -> str:
    try:
        return json.dumps(payload or {}, ensure_ascii=True, sort_keys=True)[:12000]
    except TypeError:
        return json.dumps({"unserializable": True}, ensure_ascii=True)


def _safe_response_text(response: requests.Response) -> str:
    text = (response.text or "").strip()
    if not text:
        return ""
    authorization = ""
    request = getattr(response, "request", None)
    headers = getattr(request, "headers", {}) or {}
    authorization = str(headers.get("Authorization") or "")
    if authorization:
        text = text.replace(authorization, "[redacted]")
    return text[:1500]


def _utcnow() -> datetime:
    return datetime.utcnow()


class MercadoPagoClient:
    def __init__(self, settings: PaymentSettings) -> None:
        self.settings = settings

    def _headers(self) -> dict[str, str]:
        if not self.settings.access_token:
            raise PaymentServiceError(
                503,
                "Mercado Pago no esta configurado para crear pagos.",
                "mercadopago_missing_access_token",
            )
        return {
            "Authorization": f"Bearer {self.settings.access_token}",
            "Content-Type": "application/json",
        }

    def create_preference(self, payload: dict) -> dict:
        try:
            response = requests.post(
                MERCADO_PAGO_PREFERENCES_URL,
                headers=self._headers(),
                json=payload,
                timeout=12,
            )
        except requests.RequestException as exc:
            logger.warning("mercadopago preference network_error type=%s", type(exc).__name__)
            raise PaymentServiceError(
                502,
                "No fue posible conectar con Mercado Pago para crear el checkout.",
                "mercadopago_network_error",
            ) from exc
        if response.status_code not in {200, 201}:
            logger.warning(
                "mercadopago preference rejected status=%s body=%s",
                response.status_code,
                _safe_response_text(response),
            )
            raise PaymentServiceError(
                502 if response.status_code >= 500 else 400,
                "Mercado Pago no pudo crear la preferencia de checkout.",
                "mercadopago_preference_rejected",
            )
        try:
            return response.json()
        except ValueError as exc:
            logger.warning("mercadopago preference invalid_json status=%s", response.status_code)
            raise PaymentServiceError(
                502,
                "Mercado Pago respondio con un formato invalido.",
                "mercadopago_invalid_response",
            ) from exc

    def get_payment(self, payment_id: str) -> dict:
        try:
            response = requests.get(
                MERCADO_PAGO_PAYMENT_URL.format(payment_id=payment_id),
                headers=self._headers(),
                timeout=12,
            )
        except requests.RequestException as exc:
            logger.warning("mercadopago payment lookup network_error type=%s", type(exc).__name__)
            raise PaymentServiceError(
                502,
                "No fue posible consultar el pago en Mercado Pago.",
                "mercadopago_network_error",
            ) from exc
        if response.status_code != 200:
            logger.warning("mercadopago payment lookup rejected status=%s", response.status_code)
            raise PaymentServiceError(
                502 if response.status_code >= 500 else 400,
                "No fue posible consultar el pago en Mercado Pago.",
                "mercadopago_payment_lookup_failed",
            )
        try:
            return response.json()
        except ValueError as exc:
            raise PaymentServiceError(
                502,
                "Mercado Pago respondio con un formato invalido.",
                "mercadopago_invalid_response",
            ) from exc


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

    def _payment_event(
        self,
        *,
        transaction: PaymentTransaction | None,
        reservation_id: int | None,
        event_type: str,
        previous_status: str = "",
        new_status: str = "",
        provider_event_id: str | None = None,
        raw_payload: dict | None = None,
        status: str = "processed",
    ) -> None:
        self.db.add(
            PaymentEvent(
                transaction_id=transaction.id if transaction is not None else None,
                reservation_id=reservation_id,
                provider=self.settings.provider,
                provider_event_id=provider_event_id,
                event_type=event_type,
                previous_status=previous_status,
                new_status=new_status,
                status=status,
                raw_payload_json=_safe_json(raw_payload or {}),
                processed_at=_utcnow() if status in {"processed", "duplicate", "failed"} else None,
            )
        )

    def _webhook_delivery_key(self, payload: dict, headers: dict, raw_query: str) -> str:
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        query_params = parse_qs(raw_query or "")
        provider_event_id = str(
            headers.get("x-request-id")
            or headers.get("X-Request-Id")
            or payload.get("id")
            or data.get("id")
            or (query_params.get("data.id") or query_params.get("id") or [""])[0]
            or ""
        )
        event_type = str(payload.get("type") or payload.get("action") or payload.get("topic") or "payment")
        if provider_event_id:
            return f"{self.settings.provider}:{event_type}:{provider_event_id}"
        digest = hashlib.sha256(_safe_json({"payload": payload, "query": raw_query}).encode()).hexdigest()
        return f"{self.settings.provider}:{event_type}:{digest}"

    def _record_webhook_delivery(self, payload: dict, headers: dict, raw_query: str) -> tuple[WebhookDeliveryLog, bool]:
        delivery_key = self._webhook_delivery_key(payload, headers, raw_query)
        existing = self.db.scalar(select(WebhookDeliveryLog).where(WebhookDeliveryLog.delivery_key == delivery_key))
        if existing is not None:
            existing.duplicate = True
            existing.status = "duplicate"
            existing.processed_at = existing.processed_at or _utcnow()
            self.db.add(existing)
            self.db.commit()
            return existing, True

        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        query_params = parse_qs(raw_query or "")
        provider_event_id = str(data.get("id") or payload.get("id") or (query_params.get("data.id") or query_params.get("id") or [""])[0] or "")
        delivery = WebhookDeliveryLog(
            provider=self.settings.provider,
            delivery_key=delivery_key,
            provider_event_id=provider_event_id,
            event_type=str(payload.get("type") or payload.get("action") or payload.get("topic") or "payment"),
            status="received",
            raw_payload_json=_safe_json(
                {
                    "type": payload.get("type"),
                    "action": payload.get("action"),
                    "topic": payload.get("topic"),
                    "data_id_present": bool(provider_event_id),
                    "query_present": bool(raw_query),
                }
            ),
        )
        self.db.add(delivery)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = self.db.scalar(select(WebhookDeliveryLog).where(WebhookDeliveryLog.delivery_key == delivery_key))
            if existing is not None:
                existing.duplicate = True
                existing.status = "duplicate"
                existing.processed_at = existing.processed_at or _utcnow()
                self.db.add(existing)
                self.db.commit()
                return existing, True
            raise
        self.db.refresh(delivery)
        return delivery, False

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
                apply_state_transition(
                    self.db,
                    reserva,
                    RESERVATION_EXPIRED,
                    actor=self.current_user,
                    action="reservation_payment_expired",
                )
                released += 1
            expiration.status = "released"
            expiration.released_at = now
            self.db.add(expiration)
            self._audit("reservation_payment_expired", reserva.id if reserva else None)
        if released or expirations:
            self.db.commit()
        return released

    def _preference_payload(self, reserva: Reserva, base_url: str) -> dict:
        public_base_url = self._public_base_url(base_url)
        notification_url = f"{public_base_url}/payments/webhook?source_news=webhooks"
        back_urls = self._back_urls(public_base_url, reserva.id)
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
            "back_urls": back_urls,
            "auto_return": "approved",
            "notification_url": notification_url,
            "metadata": {
                "reservation_id": reserva.id,
                "payment_mode": self.settings.mode,
            },
        }

    def _public_base_url(self, request_base_url: str) -> str:
        raw_value = (self.settings.public_base_url or request_base_url or "").strip().rstrip("/")
        if raw_value.startswith("http://") and "onrender.com" in raw_value:
            raw_value = raw_value.replace("http://", "https://", 1)
        return raw_value or "https://latiburona-1.onrender.com"

    def _back_urls(self, public_base_url: str, reservation_id: int) -> dict:
        query = urlencode({"reservation_id": reservation_id})
        return {
            "success": self.settings.success_url or f"{public_base_url}/health?payment=success&{query}",
            "failure": self.settings.failure_url or f"{public_base_url}/health?payment=failure&{query}",
            "pending": self.settings.pending_url or f"{public_base_url}/health?payment=pending&{query}",
        }

    def _validate_provider_ready(self) -> None:
        if self.settings.provider != "mercadopago":
            return
        if not self.settings.access_token:
            raise PaymentServiceError(
                503,
                "Mercado Pago no esta configurado para crear pagos.",
                "mercadopago_missing_access_token",
            )

    @staticmethod
    def _validate_amount(amount: float) -> None:
        if amount <= 0:
            raise PaymentServiceError(
                422,
                "La reserva no tiene un valor valido para generar checkout.",
                "invalid_payment_amount",
            )

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

        self._validate_amount(float(reserva.total or 0.0))
        self._validate_provider_ready()
        expires_at = _utcnow() + timedelta(minutes=self.settings.timeout_minutes)
        if reserva.estado not in {"PAID", "confirmada", RESERVATION_PAID, "confirmed"}:
            apply_state_transition(
                self.db,
                reserva,
                RESERVATION_PENDING_PAYMENT,
                actor=self.current_user,
                action="reservation_pending_payment",
                details="checkout solicitado",
            )

        provider = self.settings.provider
        preference_id = None
        payment_url = ""
        raw_payload = {}
        if provider == "mercadopago":
            preference_payload = self._preference_payload(reserva, base_url)
            logger.info(
                "payment checkout create provider=mercadopago mode=%s reservation_id=%s amount=%.2f has_public_key=%s has_access_token=%s",
                self.settings.mode,
                reserva.id,
                float(reserva.total or 0.0),
                bool(self.settings.public_key),
                bool(self.settings.access_token),
            )
            preference = self.mercado_pago.create_preference(preference_payload)
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
                "payload": {
                    "items_count": len(preference_payload.get("items", [])),
                    "currency_id": preference_payload["items"][0].get("currency_id"),
                    "external_reference": preference_payload.get("external_reference"),
                    "has_notification_url": bool(preference_payload.get("notification_url")),
                    "has_back_urls": bool(preference_payload.get("back_urls")),
                    "auto_return": preference_payload.get("auto_return"),
                },
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
        self.db.flush()
        self._payment_event(
            transaction=transaction,
            reservation_id=reserva.id,
            event_type="checkout_created",
            new_status=PAYMENT_STATUS_PENDING,
            provider_event_id=preference_id,
            raw_payload={"provider": provider, "preference_id_present": bool(preference_id)},
        )
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
        delivery, is_duplicate = self._record_webhook_delivery(payload, headers, raw_query)
        if is_duplicate:
            self._payment_event(
                transaction=None,
                reservation_id=None,
                event_type="webhook_duplicate",
                provider_event_id=delivery.provider_event_id,
                raw_payload={"delivery_key": delivery.delivery_key},
                status="duplicate",
            )
            self.db.commit()
            return {
                "ok": True,
                "duplicate": True,
                "delivery_id": delivery.id,
            }

        try:
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
                delivery.status = "accepted_unmatched"
                delivery.processed_at = _utcnow()
                self.db.add(delivery)
                self._payment_event(
                    transaction=None,
                    reservation_id=reservation_id or None,
                    event_type="webhook_unmatched",
                    provider_event_id=provider_payment_id or delivery.provider_event_id,
                    raw_payload={"external_reference": reservation_id_raw},
                    status="processed",
                )
                self.db.commit()
                raise PaymentServiceError(202, "Webhook recibido sin transaccion local asociada.")

            reserva = self.db.get(Reserva, transaction.reservation_id)
            if reserva is None:
                raise PaymentServiceError(404, "Reserva no encontrada para el pago.")

            provider_status = str(payment_data.get("status") or "").lower()
            mapped_status = self._map_provider_status(provider_status)
            previous_status = transaction.status
            already_processed = (
                previous_status == mapped_status
                and bool(provider_payment_id)
                and transaction.provider_payment_id == provider_payment_id
            )
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
                apply_state_transition(self.db, reserva, RESERVATION_PAID, action="payment_paid", details=provider_status)
                for expiration in reserva.expirations:
                    if expiration.status == "pending":
                        expiration.status = "paid"
                        self.db.add(expiration)
            elif mapped_status == PAYMENT_STATUS_FAILED:
                apply_state_transition(self.db, reserva, RESERVATION_FAILED, action="payment_failed", details=provider_status)
            elif mapped_status == PAYMENT_STATUS_CANCELLED:
                apply_state_transition(self.db, reserva, RESERVATION_CANCELLED, action="payment_cancelled", details=provider_status)
            elif mapped_status == PAYMENT_STATUS_REFUNDED:
                apply_state_transition(self.db, reserva, RESERVATION_REFUNDED, action="payment_refunded", details=provider_status)

            self.db.add(transaction)
            self.db.add(reserva)
            delivery.status = "duplicate_payment_state" if already_processed else "processed"
            delivery.processed_at = _utcnow()
            self.db.add(delivery)
            self._payment_event(
                transaction=transaction,
                reservation_id=reserva.id,
                event_type="webhook_processed" if not already_processed else "webhook_duplicate_state",
                previous_status=previous_status,
                new_status=mapped_status,
                provider_event_id=provider_payment_id or delivery.provider_event_id,
                raw_payload={"provider_status": provider_status, "delivery_id": delivery.id},
                status="duplicate" if already_processed else "processed",
            )
            if previous_status != mapped_status:
                self._audit("payment_webhook_processed", reserva.id, f"{previous_status}->{mapped_status}")
            self.db.commit()
            return {
                "ok": True,
                "reservation_id": reserva.id,
                "payment_status": transaction.status,
                "reservation_status": reserva.estado,
                "duplicate": already_processed,
                "delivery_id": delivery.id,
            }
        except ReservationStateError as exc:
            delivery.status = "state_rejected"
            delivery.error_message = str(exc)[:1200]
            delivery.processed_at = _utcnow()
            self.db.add(delivery)
            self._payment_event(
                transaction=None,
                reservation_id=None,
                event_type="webhook_state_rejected",
                provider_event_id=delivery.provider_event_id,
                raw_payload={"error": str(exc), "delivery_id": delivery.id},
                status="failed",
            )
            self.db.commit()
            raise PaymentServiceError(409, str(exc), "reservation_state_rejected") from exc
        except PaymentServiceError as exc:
            if exc.status_code != 202:
                delivery.status = "failed"
                delivery.error_message = str(exc)[:1200]
                delivery.processed_at = _utcnow()
                self.db.add(delivery)
                self._payment_event(
                    transaction=None,
                    reservation_id=None,
                    event_type="webhook_failed",
                    provider_event_id=delivery.provider_event_id,
                    raw_payload={"error": exc.code, "delivery_id": delivery.id},
                    status="failed",
                )
                self.db.commit()
            raise

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
