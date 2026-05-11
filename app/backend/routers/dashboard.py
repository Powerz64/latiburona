from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.backend.db import get_db
from app.backend.models import User
from app.backend.services.analytics_service_api import AnalyticsServiceAPI
from app.backend.services.auth_service import get_current_user, user_can_manage_global

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    overview = AnalyticsServiceAPI(db, current_user).overview()
    return {
        **overview,
        "scope": "global" if user_can_manage_global(current_user) else "own",
    }
