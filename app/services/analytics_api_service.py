from __future__ import annotations

from app.services.api_client import ApiClient, ApiResponseError
from app.utils.constants import TIME_OPTIONS


class AnalyticsApiService:
    def __init__(self, api_client: ApiClient, fallback_service=None) -> None:
        self.api_client = api_client
        self.fallback_service = fallback_service

    def _get(self, path: str) -> dict:
        response = self.api_client.request("GET", path)
        payload = self.api_client.parse_response(response)
        if response.status_code != 200:
            raise ApiResponseError(response.status_code, payload)
        return payload if isinstance(payload, dict) else {}

    def get_dashboard_metrics(self) -> dict:
        try:
            overview = self._get("/analytics/overview")
        except Exception:
            if self.fallback_service is not None:
                return self.fallback_service.get_dashboard_metrics()
            raise
        status_confirmed = int(overview.get("confirmed_reservations", 0) or 0)
        status_pending = int(overview.get("pending_reservations", 0) or 0)
        total_revenue = float(overview.get("revenue", 0.0) or 0.0)
        total_reservations = int(overview.get("reservations", 0) or 0)
        occupancy = float(overview.get("occupancy", 0.0) or 0.0)
        peak_hour = str(overview.get("peak_hour") or "Sin datos")
        top_court = str(overview.get("top_court") or "--")
        reservations_by_hour = dict(overview.get("reservations_by_hour") or {})
        for hour in TIME_OPTIONS:
            reservations_by_hour.setdefault(hour, 0)
        least_hour = min(TIME_OPTIONS, key=lambda hour: (reservations_by_hour.get(hour, 0), hour)) if reservations_by_hour else "Sin datos"
        peak_ranges = [(peak_hour, reservations_by_hour.get(peak_hour, 0))] if peak_hour != "Sin datos" else []

        insights = [
            f"Cancha lider: {top_court}.",
            f"Reservas confirmadas: {status_confirmed}; pendientes: {status_pending}.",
            f"Ingreso semanal: {float(overview.get('revenue_week', 0.0) or 0.0):,.0f} COP.",
        ]
        recommendations = [
            "Priorizar confirmacion de reservas pendientes.",
            "Revisar ocupacion por cancha antes de lanzar promociones.",
            "Usar hora pico para ajustar operacion y personal.",
        ]

        return {
            "total_reservations": total_reservations,
            "total_revenue": total_revenue,
            "confirmed_revenue": total_revenue,
            "pending_revenue": 0.0,
            "revenue_today": float(overview.get("revenue_today", 0.0) or 0.0),
            "revenue_week": float(overview.get("revenue_week", 0.0) or 0.0),
            "confirmed_reservations": status_confirmed,
            "pending_reservations": status_pending,
            "top_court": top_court,
            "most_requested_hour": peak_hour,
            "least_requested_hour": least_hour,
            "peak_ranges": peak_ranges,
            "reservations_by_hour": reservations_by_hour,
            "occupancy_rate": occupancy,
            "occupancy_by_court": list(overview.get("occupancy_by_court") or []),
            "reservations_trend": list(overview.get("reservations_trend") or []),
            "revenue_trend": list(overview.get("revenue_trend") or []),
            "weekly_summary": dict(overview.get("weekly_summary") or {}),
            "monthly_summary": dict(overview.get("monthly_summary") or {}),
            "insights": insights,
            "recommendations": recommendations,
            "headline_insight": insights[0],
            "primary_recommendation": recommendations[0],
        }
