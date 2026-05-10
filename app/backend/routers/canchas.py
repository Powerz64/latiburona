from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.db import get_db
from app.backend.models import Cancha
from app.backend.schemas import CanchaOut

router = APIRouter(prefix="/canchas", tags=["canchas"])


@router.get("", response_model=list[CanchaOut])
def list_canchas(db: Session = Depends(get_db)) -> list[Cancha]:
    return list(db.scalars(select(Cancha).order_by(Cancha.nombre.asc())).all())
