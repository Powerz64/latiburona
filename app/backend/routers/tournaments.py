from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.db import get_db
from app.backend.models import Torneo, User
from app.backend.schemas import TorneoCreate, TorneoOut, TorneoUpdate
from app.backend.services.auth_service import ROLE_ADMIN, ROLE_OPERATOR, get_current_user, require_role, user_can_manage_global

router = APIRouter(prefix="/torneos", tags=["torneos"])


@router.get("", response_model=list[TorneoOut])
def list_torneos(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Torneo]:
    query = select(Torneo).order_by(Torneo.created_at.desc(), Torneo.nombre.asc())
    if not user_can_manage_global(current_user):
        query = query.where(Torneo.user_id == current_user.id)
    return list(db.scalars(query).all())


@router.get("/{torneo_id}", response_model=TorneoOut)
def get_torneo(
    torneo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Torneo:
    query = select(Torneo).where(Torneo.id == torneo_id)
    if not user_can_manage_global(current_user):
        query = query.where(Torneo.user_id == current_user.id)
    torneo = db.scalar(query)
    if torneo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Torneo no encontrado")
    return torneo


@router.post("", response_model=TorneoOut, status_code=status.HTTP_201_CREATED)
def create_torneo(
    payload: TorneoCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR)),
) -> Torneo:
    torneo = Torneo(user_id=current_user.id, **payload.model_dump())
    db.add(torneo)
    db.commit()
    db.refresh(torneo)
    return torneo


@router.put("/{torneo_id}", response_model=TorneoOut)
def update_torneo(
    torneo_id: int,
    payload: TorneoUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR)),
) -> Torneo:
    query = select(Torneo).where(Torneo.id == torneo_id)
    if not user_can_manage_global(current_user):
        query = query.where(Torneo.user_id == current_user.id)
    torneo = db.scalar(query)
    if torneo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Torneo no encontrado")
    for key, value in payload.model_dump().items():
        setattr(torneo, key, value)
    db.add(torneo)
    db.commit()
    db.refresh(torneo)
    return torneo


@router.delete("/{torneo_id}", status_code=status.HTTP_200_OK)
def delete_torneo(
    torneo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR)),
) -> dict:
    query = select(Torneo).where(Torneo.id == torneo_id)
    if not user_can_manage_global(current_user):
        query = query.where(Torneo.user_id == current_user.id)
    torneo = db.scalar(query)
    if torneo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Torneo no encontrado")
    db.delete(torneo)
    db.commit()
    return {"message": "Torneo eliminado correctamente"}
