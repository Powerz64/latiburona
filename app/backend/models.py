from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.db import Base


class Cancha(Base):
    __tablename__ = "canchas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    direccion: Mapped[str] = mapped_column(String(200))
    ubicacion: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[str] = mapped_column(String(80), default="Futbol 5")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    reservas: Mapped[list["Reserva"]] = relationship(back_populates="cancha")
    promociones: Mapped[list["Promotion"]] = relationship(back_populates="cancha")


class Reserva(Base):
    __tablename__ = "reservas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    cancha_id: Mapped[int] = mapped_column(ForeignKey("canchas.id"), index=True)
    fecha: Mapped[str] = mapped_column(String(10), index=True)
    hora_inicio: Mapped[str] = mapped_column(String(5), index=True)
    hora_fin: Mapped[str] = mapped_column(String(5), index=True)
    estado: Mapped[str] = mapped_column(String(20), default="pendiente", index=True)
    total: Mapped[float] = mapped_column(Float, default=0.0)
    subtotal: Mapped[float] = mapped_column(Float, default=0.0)
    descuento: Mapped[float] = mapped_column(Float, default=0.0)
    jornada: Mapped[str] = mapped_column(String(30), default="Manana")
    client_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(30))
    address: Mapped[str] = mapped_column(String(200))
    people_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    state_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User | None"] = relationship(back_populates="reservas")
    cancha: Mapped[Cancha] = relationship(back_populates="reservas")
    payment_transactions: Mapped[list["PaymentTransaction"]] = relationship(back_populates="reservation")
    public_links: Mapped[list["ReservationPublicLink"]] = relationship(back_populates="reservation")
    expirations: Mapped[list["ReservationExpiration"]] = relationship(back_populates="reservation")


class Torneo(Base):
    __tablename__ = "torneos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    nombre: Mapped[str] = mapped_column(String(140), index=True)
    categoria: Mapped[str] = mapped_column(String(80))
    participantes: Mapped[str] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(20), default="activo", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User | None"] = relationship(back_populates="torneos")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(140))
    display_name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="client", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    reservas: Mapped[list[Reserva]] = relationship(back_populates="user")
    torneos: Mapped[list[Torneo]] = relationship(back_populates="user")


class AppSettingRecord(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Promotion(Base):
    __tablename__ = "promotions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cancha_id: Mapped[int | None] = mapped_column(ForeignKey("canchas.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(140), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    discount_percent: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    cancha: Mapped[Cancha | None] = relationship(back_populates="promociones")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reservation_id: Mapped[int] = mapped_column(ForeignKey("reservas.id"), index=True)
    provider: Mapped[str] = mapped_column(String(40), default="manual", index=True)
    provider_payment_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    provider_preference_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), default="COP")
    payment_url: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    raw_payload_json: Mapped[str] = mapped_column(Text, default="")

    reservation: Mapped[Reserva] = relationship(back_populates="payment_transactions")


class PaymentEvent(Base):
    __tablename__ = "payment_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("payment_transactions.id"), nullable=True, index=True)
    reservation_id: Mapped[int | None] = mapped_column(ForeignKey("reservas.id"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(40), default="manual", index=True)
    provider_event_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(80), default="payment_event", index=True)
    previous_status: Mapped[str] = mapped_column(String(30), default="")
    new_status: Mapped[str] = mapped_column(String(30), default="")
    status: Mapped[str] = mapped_column(String(30), default="processed", index=True)
    raw_payload_json: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)


class WebhookDeliveryLog(Base):
    __tablename__ = "webhook_delivery_logs"
    __table_args__ = (UniqueConstraint("delivery_key", name="uq_webhook_delivery_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(40), default="mercadopago", index=True)
    delivery_key: Mapped[str] = mapped_column(String(160), index=True)
    provider_event_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(80), default="", index=True)
    status: Mapped[str] = mapped_column(String(30), default="received", index=True)
    duplicate: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    error_message: Mapped[str] = mapped_column(Text, default="")
    raw_payload_json: Mapped[str] = mapped_column(Text, default="")
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)


class ReservationPublicLink(Base):
    __tablename__ = "reservation_public_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reservation_id: Mapped[int] = mapped_column(ForeignKey("reservas.id"), index=True)
    token: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    reservation: Mapped[Reserva] = relationship(back_populates="public_links")


class ReservationExpiration(Base):
    __tablename__ = "reservation_expirations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reservation_id: Mapped[int] = mapped_column(ForeignKey("reservas.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)

    reservation: Mapped[Reserva] = relationship(back_populates="expirations")
