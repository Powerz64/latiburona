from __future__ import annotations

import traceback

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.backend.db import get_db
from app.backend.schemas import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    UserPublic,
)
from app.backend.services.auth_service import (
    AuthServiceError,
    authenticate_user,
    create_token_bundle,
    get_current_user,
    refresh_session,
    register_user,
    serialize_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    try:
        user = register_user(db, payload)
    except AuthServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    return {
        "message": "Cuenta creada correctamente. Ya puedes iniciar sesion.",
        "user": serialize_user(user),
    }


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    print("LOGIN REQUEST RECEIVED", flush=True)
    print("EMAIL:", str(payload.email).strip().lower(), flush=True)
    try:
        user = authenticate_user(db, payload)
    except AuthServiceError as exc:
        print("LOGIN ERROR:", exc.message, flush=True)
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    except Exception as exc:
        print("LOGIN ERROR:", exc, flush=True)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))

    try:
        return create_token_bundle(user)
    except Exception as exc:
        print("LOGIN ERROR:", exc, flush=True)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/refresh", response_model=LoginResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> dict:
    try:
        user = refresh_session(db, payload.refresh_token)
        return create_token_bundle(user)
    except AuthServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/me", response_model=UserPublic)
def me(current_user=Depends(get_current_user)) -> dict:
    return serialize_user(current_user)


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(_payload: LogoutRequest | None = None) -> dict:
    return {"message": "Sesion cerrada correctamente"}
