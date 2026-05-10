from __future__ import annotations

import sqlite3
import os
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.backend.config import (
    database_backend_name,
    get_required_secret_key,
    get_sqlite_fallback_path,
    normalize_database_url,
)
from app.utils.constants import LOCATION_INFO, SERVICE_TYPES
from app.utils.paths import DATABASE_PATH
from app.utils.time_slots import next_time_value

SERVER_DB_PATH = get_sqlite_fallback_path()
SQLALCHEMY_DATABASE_URL = normalize_database_url(os.getenv("DATABASE_URL"))
DATABASE_BACKEND = database_backend_name(SQLALCHEMY_DATABASE_URL)
ENGINE_CONNECT_ARGS = {"check_same_thread": False} if DATABASE_BACKEND == "sqlite" else {}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=ENGINE_CONNECT_ARGS,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _default_canchas() -> list[dict]:
    return [
        {
            "nombre": name,
            "direccion": LOCATION_INFO["direccion"],
            "ubicacion": LOCATION_INFO["puntos_referencia"],
        }
        for name in SERVICE_TYPES
    ]


def _parse_legacy_datetime(raw_value: str | None) -> datetime:
    if not raw_value:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(raw_value)
    except ValueError:
        try:
            return datetime.strptime(raw_value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return datetime.utcnow()


def _seed_canchas(session: Session) -> None:
    from app.backend.models import Cancha

    existing = {
        cancha.nombre
        for cancha in session.scalars(select(Cancha)).all()
    }
    for item in _default_canchas():
        if item["nombre"] in existing:
            continue
        session.add(Cancha(**item))
    session.commit()


def _ensure_schema_compatibility() -> None:
    inspector = inspect(engine)
    with engine.begin() as connection:
        users_columns = {column["name"] for column in inspector.get_columns("users")} if inspector.has_table("users") else set()
        reservas_columns = {column["name"] for column in inspector.get_columns("reservas")} if inspector.has_table("reservas") else set()
        torneos_columns = {column["name"] for column in inspector.get_columns("torneos")} if inspector.has_table("torneos") else set()

        if "role" not in users_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'client'"))
        if "is_active" not in users_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE"))
        if "user_id" not in reservas_columns:
            connection.execute(text("ALTER TABLE reservas ADD COLUMN user_id INTEGER"))
        if "user_id" not in torneos_columns:
            connection.execute(text("ALTER TABLE torneos ADD COLUMN user_id INTEGER"))


def _backfill_user_roles(session: Session) -> None:
    session.execute(
        text(
            """
            UPDATE users
            SET role = CASE
                WHEN COALESCE(is_admin, 0) = 1 THEN 'admin'
                ELSE 'client'
            END
            WHERE role IS NULL OR TRIM(role) = ''
            """
        )
    )
    session.execute(text("UPDATE users SET is_active = TRUE WHERE is_active IS NULL"))
    session.execute(text("UPDATE users SET is_admin = TRUE WHERE role = 'admin'"))
    session.commit()


def _ensure_cancha(session: Session, nombre: str) -> int:
    from app.backend.models import Cancha

    cancha = session.scalar(select(Cancha).where(Cancha.nombre == nombre))
    if cancha:
        return cancha.id

    cancha = Cancha(
        nombre=nombre,
        direccion=LOCATION_INFO["direccion"],
        ubicacion=LOCATION_INFO["puntos_referencia"],
    )
    session.add(cancha)
    session.commit()
    session.refresh(cancha)
    return cancha.id


def _migrate_legacy_reservas(session: Session) -> None:
    from app.backend.models import Reserva

    if session.scalar(select(Reserva.id).limit(1)) is not None:
        return
    if not DATABASE_PATH or not Path(DATABASE_PATH).exists():
        return

    legacy_db = sqlite3.connect(DATABASE_PATH)
    legacy_db.row_factory = sqlite3.Row
    try:
        rows = legacy_db.execute("SELECT * FROM reservations ORDER BY id ASC").fetchall()
    finally:
        legacy_db.close()

    for row in rows:
        cancha_id = _ensure_cancha(session, row["service_type"])
        hora_inicio = row["start_time"] or row["reservation_time"]
        hora_fin = row["end_time"] or next_time_value(hora_inicio)
        session.add(
            Reserva(
                cancha_id=cancha_id,
                fecha=row["reservation_date"],
                hora_inicio=hora_inicio,
                hora_fin=hora_fin,
                estado=row["status"],
                total=float(row["total"]),
                subtotal=float(row["subtotal"]),
                descuento=float(row["discount"]),
                jornada=row["schedule"],
                client_name=row["client_name"],
                phone=row["phone"],
                address=row["address"],
                people_count=int(row["people_count"]),
                created_at=_parse_legacy_datetime(row["created_at"]),
            )
        )
    session.commit()


def _migrate_legacy_torneos(session: Session) -> None:
    from app.backend.models import Torneo

    if session.scalar(select(Torneo.id).limit(1)) is not None:
        return
    if not DATABASE_PATH or not Path(DATABASE_PATH).exists():
        return

    legacy_db = sqlite3.connect(DATABASE_PATH)
    legacy_db.row_factory = sqlite3.Row
    try:
        rows = legacy_db.execute("SELECT * FROM tournaments ORDER BY id ASC").fetchall()
    finally:
        legacy_db.close()

    for row in rows:
        session.add(
            Torneo(
                nombre=row["name"],
                categoria=row["category"],
                participantes=row["participants"],
                estado=row["status"],
                created_at=_parse_legacy_datetime(row["created_at"]),
            )
        )
    session.commit()


def init_db() -> None:
    from app.backend import models  # noqa: F401
    from app.backend.services.auth_service import seed_admin_user

    get_required_secret_key()
    Base.metadata.create_all(bind=engine)
    _ensure_schema_compatibility()
    with SessionLocal() as session:
        session.execute(text("SELECT 1"))
        _backfill_user_roles(session)
        _seed_canchas(session)
        _migrate_legacy_reservas(session)
        _migrate_legacy_torneos(session)
        seed_admin_user(session)
