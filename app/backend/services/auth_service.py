from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.config import get_required_secret_key
from app.backend.db import get_db
from app.backend.models import User
from app.backend.schemas import LoginRequest, RegisterRequest

logger = logging.getLogger(__name__)

ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7
ALGORITHM = "HS256"

ROLE_ADMIN = "admin"
ROLE_OPERATOR = "operator"
ROLE_CLIENT = "client"
ALLOWED_ROLES = {ROLE_ADMIN, ROLE_OPERATOR, ROLE_CLIENT}
MANAGER_ROLES = {ROLE_ADMIN, ROLE_OPERATOR}

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"

ADMIN_EMAIL = "admin@latiburona.com"
ADMIN_FULL_NAME = "Miguel Cuello"
ADMIN_DISPLAY_NAME = "Miguel"
DEFAULT_BOOTSTRAP_ADMIN_EMAIL = "cuellomiguel61@latiburona.com"
DEFAULT_BOOTSTRAP_ADMIN_PASSWORD = "Mary2716@"
DEFAULT_BOOTSTRAP_ADMIN_FULL_NAME = "Miguel Cuello"
DEFAULT_BOOTSTRAP_ADMIN_DISPLAY_NAME = "Miguel"

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


@dataclass
class AuthServiceError(Exception):
    status_code: int
    message: str

    def __str__(self) -> str:
        return self.message


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_role(role: str | None, *, is_admin: bool = False) -> str:
    if is_admin:
        return ROLE_ADMIN
    normalized = str(role or "").strip().lower()
    return normalized if normalized in ALLOWED_ROLES else ROLE_CLIENT


def user_is_admin(user: User) -> bool:
    return normalize_role(user.role, is_admin=bool(user.is_admin)) == ROLE_ADMIN


def user_can_manage_global(user: User) -> bool:
    return normalize_role(user.role, is_admin=bool(user.is_admin)) in MANAGER_ROLES


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return password_context.verify(plain_password, password_hash)
    except Exception as exc:
        logger.exception("Error verificando el password hash del usuario.")
        raise AuthServiceError(500, f"Error verificando credenciales: {exc}") from exc


def hash_password(password: str) -> str:
    return password_context.hash(password)


def _encode_token(payload: dict) -> str:
    return jwt.encode(payload, get_required_secret_key(), algorithm=ALGORITHM)


def create_access_token(user: User) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "role": normalize_role(user.role, is_admin=bool(user.is_admin)),
        "type": TOKEN_TYPE_ACCESS,
        "exp": expires_at,
    }
    return _encode_token(payload)


def create_refresh_token(user: User) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": normalize_role(user.role, is_admin=bool(user.is_admin)),
        "type": TOKEN_TYPE_REFRESH,
        "exp": expires_at,
    }
    return _encode_token(payload)


def create_token_bundle(user: User) -> dict:
    return {
        "access_token": create_access_token(user),
        "refresh_token": create_refresh_token(user),
        "token_type": "bearer",
        "user": serialize_user(user),
    }


def serialize_user(user: User) -> dict:
    role = normalize_role(user.role, is_admin=bool(user.is_admin))
    return {
        "id": user.id,
        "full_name": user.full_name,
        "display_name": user.display_name,
        "email": user.email,
        "role": role,
        "is_active": bool(user.is_active),
        "is_admin": role == ROLE_ADMIN,
    }


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == normalize_email(email)))


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def register_user(db: Session, payload: RegisterRequest) -> User:
    email = normalize_email(str(payload.email))
    confirm_email = normalize_email(str(payload.confirm_email))

    if email != confirm_email:
        raise AuthServiceError(400, "Los correos electronicos no coinciden.")
    if payload.password != payload.confirm_password:
        raise AuthServiceError(400, "Las contrasenas no coinciden.")
    if get_user_by_email(db, email) is not None:
        raise AuthServiceError(409, "Ya existe una cuenta con este correo electronico.")

    user = User(
        full_name=payload.full_name.strip(),
        display_name=payload.display_name.strip(),
        email=email,
        phone=payload.phone.strip() or None,
        password_hash=hash_password(payload.password),
        role=ROLE_CLIENT,
        is_active=True,
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, payload: LoginRequest) -> User:
    user = get_user_by_email(db, str(payload.email))
    if user is None:
        raise AuthServiceError(401, "Correo o contrasena incorrectos.")
    if not user.is_active:
        raise AuthServiceError(403, "La cuenta no se encuentra activa.")
    if not user.password_hash:
        raise AuthServiceError(500, "El usuario no tiene un password hash valido en la base de datos.")
    if not verify_password(payload.password, user.password_hash):
        raise AuthServiceError(401, "Correo o contrasena incorrectos.")
    user.role = normalize_role(user.role, is_admin=bool(user.is_admin))
    user.is_admin = user.role == ROLE_ADMIN
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _decode_token(token: str, *, expected_type: str) -> dict:
    try:
        payload = jwt.decode(token, get_required_secret_key(), algorithms=[ALGORITHM])
    except JWTError as exc:
        raise AuthServiceError(status.HTTP_401_UNAUTHORIZED, "No fue posible validar la sesion actual.") from exc

    token_type = str(payload.get("type") or "").strip().lower()
    if token_type != expected_type:
        raise AuthServiceError(status.HTTP_401_UNAUTHORIZED, "El token entregado no corresponde a esta operacion.")
    return payload


def refresh_session(db: Session, refresh_token: str) -> User:
    payload = _decode_token(refresh_token, expected_type=TOKEN_TYPE_REFRESH)
    try:
        user_id = int(payload.get("sub", "0"))
    except ValueError as exc:
        raise AuthServiceError(status.HTTP_401_UNAUTHORIZED, "No fue posible validar la sesion actual.") from exc

    user = get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise AuthServiceError(status.HTTP_401_UNAUTHORIZED, "No fue posible validar la sesion actual.")
    return user


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No fue posible validar la sesion actual.",
    )

    try:
        payload = _decode_token(token, expected_type=TOKEN_TYPE_ACCESS)
        user_id = int(payload.get("sub", "0"))
    except (AuthServiceError, ValueError):
        raise credentials_error

    user = get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise credentials_error
    return user


def require_role(*roles: str) -> Callable[[User], User]:
    normalized_roles = {normalize_role(role) for role in roles}

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        user_role = normalize_role(current_user.role, is_admin=bool(current_user.is_admin))
        if user_role not in normalized_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No cuentas con permisos para realizar esta accion.",
            )
        return current_user

    return dependency


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not user_is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo un administrador puede realizar esta accion.",
        )
    return current_user


def seed_admin_user(db: Session) -> None:
    admin_password = os.getenv("LATIBURONA_ADMIN_PASSWORD", "").strip()
    user = get_user_by_email(db, ADMIN_EMAIL)
    if user is not None:
        user.role = ROLE_ADMIN
        user.is_active = True
        user.is_admin = True
        db.add(user)
        db.commit()
        return
    if not admin_password:
        logger.warning(
            "LATIBURONA_ADMIN_PASSWORD no configurada; se omite la creacion del usuario admin por defecto."
        )
        return

    user = User(
        full_name=ADMIN_FULL_NAME,
        display_name=ADMIN_DISPLAY_NAME,
        email=ADMIN_EMAIL,
        phone=None,
        password_hash=hash_password(admin_password),
        role=ROLE_ADMIN,
        is_active=True,
        is_admin=True,
    )
    db.add(user)
    db.commit()
    logger.info("Usuario admin inicial creado para %s.", ADMIN_EMAIL)


def reset_admin_user(db: Session, admin_password: str) -> User:
    normalized_password = admin_password.strip()
    if not normalized_password:
        raise ValueError("Se requiere LATIBURONA_ADMIN_PASSWORD para actualizar el admin.")

    user = get_user_by_email(db, ADMIN_EMAIL)
    if user is None:
        user = User(
            full_name=ADMIN_FULL_NAME,
            display_name=ADMIN_DISPLAY_NAME,
            email=ADMIN_EMAIL,
            phone=None,
            password_hash=hash_password(normalized_password),
            role=ROLE_ADMIN,
            is_active=True,
            is_admin=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("Usuario admin creado manualmente para %s.", ADMIN_EMAIL)
        return user

    user.full_name = ADMIN_FULL_NAME
    user.display_name = ADMIN_DISPLAY_NAME
    user.password_hash = hash_password(normalized_password)
    user.role = ROLE_ADMIN
    user.is_active = True
    user.is_admin = True
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Contrasena del usuario admin actualizada para %s.", ADMIN_EMAIL)
    return user


def ensure_default_admin_user(db: Session) -> User:
    try:
        user = get_user_by_email(db, DEFAULT_BOOTSTRAP_ADMIN_EMAIL)
        if user is None:
            user = User(
                full_name=DEFAULT_BOOTSTRAP_ADMIN_FULL_NAME,
                display_name=DEFAULT_BOOTSTRAP_ADMIN_DISPLAY_NAME,
                email=normalize_email(DEFAULT_BOOTSTRAP_ADMIN_EMAIL),
                phone=None,
                password_hash=hash_password(DEFAULT_BOOTSTRAP_ADMIN_PASSWORD),
                role=ROLE_ADMIN,
                is_active=True,
                is_admin=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print("ADMIN CREATED", flush=True)
            return user

        user.full_name = DEFAULT_BOOTSTRAP_ADMIN_FULL_NAME
        user.display_name = DEFAULT_BOOTSTRAP_ADMIN_DISPLAY_NAME
        user.role = ROLE_ADMIN
        user.is_active = True
        user.is_admin = True

        if not user.password_hash or not verify_password(DEFAULT_BOOTSTRAP_ADMIN_PASSWORD, user.password_hash):
            user.password_hash = hash_password(DEFAULT_BOOTSTRAP_ADMIN_PASSWORD)

        db.add(user)
        db.commit()
        db.refresh(user)
        print("ADMIN EXISTS", flush=True)
        return user
    except Exception as exc:
        db.rollback()
        print(f"ADMIN ERROR: {exc}", flush=True)
        raise
