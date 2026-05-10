from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.db import Base


class Cancha(Base):
    __tablename__ = "canchas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    direccion: Mapped[str] = mapped_column(String(200))
    ubicacion: Mapped[str] = mapped_column(String(200))

    reservas: Mapped[list["Reserva"]] = relationship(back_populates="cancha")


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

    user: Mapped["User | None"] = relationship(back_populates="reservas")
    cancha: Mapped[Cancha] = relationship(back_populates="reservas")


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
