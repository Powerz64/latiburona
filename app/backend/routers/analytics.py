from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.backend.db import get_db
from app.backend.models import User
from app.backend.services.analytics_service_api import AnalyticsServiceAPI
from app.backend.services.auth_service import get_current_user

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnalyticsServiceAPI:
    return AnalyticsServiceAPI(db, current_user)


@router.get("/overview")
def analytics_overview(service: AnalyticsServiceAPI = Depends(_service)) -> dict:
    return service.overview()


@router.get("/operations")
def operations_health(service: AnalyticsServiceAPI = Depends(_service)) -> dict:
    return service.operations_health()


@router.get("/reservations-by-day")
def reservations_by_day(service: AnalyticsServiceAPI = Depends(_service)) -> dict:
    return service.reservations_by_day()


@router.get("/revenue-by-day")
def revenue_by_day(service: AnalyticsServiceAPI = Depends(_service)) -> dict:
    return service.revenue_by_day()


@router.get("/occupancy-by-court")
def occupancy_by_court(service: AnalyticsServiceAPI = Depends(_service)) -> dict:
    return service.occupancy_by_court()


@router.get("/peak-hours")
def peak_hours(service: AnalyticsServiceAPI = Depends(_service)) -> dict:
    return service.peak_hours()


@router.get("/status-breakdown")
def status_breakdown(service: AnalyticsServiceAPI = Depends(_service)) -> dict:
    return service.status_breakdown()


@router.get("/top-courts")
def top_courts(service: AnalyticsServiceAPI = Depends(_service)) -> dict:
    return service.top_courts()


@router.get("/weekly-summary")
def weekly_summary(service: AnalyticsServiceAPI = Depends(_service)) -> dict:
    return service.weekly_summary()


@router.get("/monthly-summary")
def monthly_summary(service: AnalyticsServiceAPI = Depends(_service)) -> dict:
    return service.monthly_summary()
