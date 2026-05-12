from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from app.utils.constants import SCHEDULE_LABELS, SERVICE_TYPES, TIME_OPTIONS
from app.utils.time_slots import hour_slots_between, week_dates

WEEKDAY_LABELS = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]


class AnalyticsService:
    def __init__(self, reservation_service) -> None:
        self.reservation_service = reservation_service

    def _reservations(self):
        return [
            item
            for item in self.reservation_service.get_all_reservations()
            if item.status not in {"cancelada", "CANCELLED", "FAILED", "REFUNDED", "EXPIRED"}
        ]

    def _hour_counts(self) -> Counter:
        counter: Counter = Counter()
        for reservation in self._reservations():
            for slot_time in hour_slots_between(reservation.start_time, reservation.end_time):
                counter[slot_time] += 1
        return counter

    def _range_counts(self) -> Counter:
        return Counter(item.time_range for item in self._reservations())

    def _build_kpi(self, value, status_label: str, color: str, caption: str) -> dict:
        return {
            "value": value,
            "label": status_label,
            "color": color,
            "caption": caption,
        }

    def _occupancy_status(self, occupancy: float) -> dict:
        if occupancy >= 80:
            return self._build_kpi(occupancy, "Alta ocupacion", "success", "Capacidad usada de forma sobresaliente")
        if occupancy >= 50:
            return self._build_kpi(occupancy, "Ocupacion media", "primary", "Todavia existe margen para escalar")
        return self._build_kpi(occupancy, "Baja ocupacion", "danger", "Conviene activar demanda y promociones")

    def _reservation_status(self, total_reservations: int) -> dict:
        if total_reservations >= 12:
            return self._build_kpi(total_reservations, "Alta actividad", "success", "Demanda robusta en el sistema")
        if total_reservations >= 6:
            return self._build_kpi(total_reservations, "Actividad estable", "primary", "Volumen comercial saludable")
        return self._build_kpi(total_reservations, "Actividad baja", "danger", "Se recomienda reforzar captacion")

    def _revenue_status(self, total_revenue: float) -> dict:
        if total_revenue >= 700000:
            return self._build_kpi(total_revenue, "Ingresos fuertes", "success", "Buen rendimiento de monetizacion")
        if total_revenue >= 300000:
            return self._build_kpi(total_revenue, "Ingresos estables", "primary", "Base solida para crecer")
        return self._build_kpi(total_revenue, "Ingresos bajos", "danger", "Hace falta empujar conversion")

    def _peak_hour_status(self, hour: str, peak_count: int, total_slots: int) -> dict:
        if hour == "Sin datos":
            return self._build_kpi(hour, "Sin demanda", "danger", "Aun no existe historial util")

        concentration = (peak_count / total_slots) if total_slots else 0
        if concentration >= 0.2:
            return self._build_kpi(hour, "Hora dominante", "success", "La demanda se concentra con claridad")
        if concentration >= 0.12:
            return self._build_kpi(hour, "Hora destacada", "primary", "Hay un patron horario visible")
        return self._build_kpi(hour, "Demanda dispersa", "warning", "La demanda se reparte entre varias horas")

    def total_reservations(self) -> int:
        return len(self._reservations())

    def total_revenue(self, status: str | None = None) -> float:
        reservations = self._reservations()
        if status is not None:
            reservations = [item for item in reservations if item.status == status]
        return round(sum(item.total for item in reservations), 2)

    def total_reserved_hours(self) -> int:
        return sum(item.duration_hours for item in self._reservations())

    def most_requested_hour(self) -> str:
        hour_counts = self._hour_counts()
        if not hour_counts:
            return "Sin datos"
        return max(TIME_OPTIONS, key=lambda hour: (hour_counts.get(hour, 0), hour))

    def least_requested_hour(self) -> str:
        hour_counts = self._hour_counts()
        if not hour_counts:
            return "Sin datos"
        return min(TIME_OPTIONS, key=lambda hour: (hour_counts.get(hour, 0), hour))

    def occupancy_rate(self, available_slots: int | None = None) -> float:
        occupied_slots = self.total_reserved_hours()
        if available_slots is None:
            unique_dates = {item.reservation_date for item in self._reservations()}
            if not unique_dates:
                unique_dates = {date.today().isoformat()}
            available_slots = max(len(unique_dates) * len(SERVICE_TYPES) * len(TIME_OPTIONS), 1)
        return round((occupied_slots / available_slots) * 100, 2)

    def reservations_by_hour(self) -> dict[str, int]:
        hour_counts = self._hour_counts()
        return {hour: hour_counts.get(hour, 0) for hour in TIME_OPTIONS}

    def schedule_distribution(self) -> dict[str, int]:
        counts = Counter()
        for reservation in self._reservations():
            for slot_time in hour_slots_between(reservation.start_time, reservation.end_time):
                schedule, _ = self.reservation_service.pricing_service.get_schedule_and_base_price(slot_time)
                counts[schedule] += 1
        return {label: counts.get(label, 0) for label in SCHEDULE_LABELS}

    def peak_ranges(self) -> list[tuple[str, int]]:
        return self._range_counts().most_common(3)

    def occupancy_heatmap(self, reference_date: str | None = None) -> dict:
        current_week = week_dates(reference_date)
        reservations = self._reservations()
        week_lookup = {current.isoformat(): current for current in current_week}
        counts = Counter()

        for reservation in reservations:
            if reservation.reservation_date not in week_lookup:
                continue
            for slot_time in hour_slots_between(reservation.start_time, reservation.end_time):
                counts[(reservation.reservation_date, slot_time)] += 1

        columns = [
            {
                "date": current.isoformat(),
                "label": current.strftime("%d/%m"),
                "weekday": WEEKDAY_LABELS[current.weekday()],
            }
            for current in current_week
        ]
        rows = []
        for slot_time in TIME_OPTIONS:
            cells = []
            for column in columns:
                count = counts.get((column["date"], slot_time), 0)
                if count == 0:
                    tone = "neutral"
                elif count >= len(SERVICE_TYPES):
                    tone = "danger"
                elif count >= max(2, len(SERVICE_TYPES) // 2):
                    tone = "warning"
                else:
                    tone = "primary"
                cells.append(
                    {
                        "date": column["date"],
                        "time": slot_time,
                        "count": count,
                        "tone": tone,
                        "label": str(count),
                    }
                )
            rows.append({"time": slot_time, "cells": cells})

        return {"columns": columns, "rows": rows}

    def generate_insights(self) -> list[str]:
        reservations = self._reservations()
        total = len(reservations)
        occupancy = self.occupancy_rate()
        schedule_counts = self.schedule_distribution()
        insights: list[str] = []

        if total == 0:
            return ["Aun no hay reservas; conviene activar una promocion de lanzamiento."]

        total_slots = max(sum(schedule_counts.values()), 1)
        night_share = schedule_counts["Noche"] / total_slots
        morning_share = schedule_counts["Manana"] / total_slots
        afternoon_share = schedule_counts["Tarde"] / total_slots
        pending_share = len([item for item in reservations if item.status == "pendiente"]) / total

        if night_share >= 0.4:
            insights.append("Alta demanda en horario nocturno.")
        if morning_share <= 0.2:
            insights.append("Baja ocupacion en la manana.")
        if 0.25 <= afternoon_share <= 0.45:
            insights.append("La tarde mantiene un volumen equilibrado de reservas.")

        least_hour = self.least_requested_hour()
        if least_hour != "Sin datos":
            insights.append(f"Se detecta baja traccion alrededor de las {least_hour}.")

        if occupancy < 50:
            insights.append("La ocupacion general esta por debajo del objetivo comercial.")
        elif occupancy >= 80:
            insights.append("La operacion trabaja cerca de alta ocupacion y permite optimizar precio.")

        if pending_share >= 0.4:
            insights.append("Existe un bloque importante de reservas pendientes por confirmar.")

        return insights[:4]

    def generate_recommendations(self) -> list[str]:
        reservations = self._reservations()
        total = len(reservations)
        occupancy = self.occupancy_rate()
        schedule_counts = self.schedule_distribution()
        total_slots = max(sum(schedule_counts.values()), 1)
        night_share = schedule_counts["Noche"] / total_slots
        morning_share = schedule_counts["Manana"] / total_slots
        pending_count = len([item for item in reservations if item.status == "pendiente"])
        recommendations: list[str] = []

        if occupancy < 50:
            recommendations.append("Aplicar promociones para elevar la ocupacion general del sistema.")
        elif occupancy >= 80:
            recommendations.append("Aprovechar la alta ocupacion con paquetes premium y cupos priorizados.")
        else:
            recommendations.append("Mantener una estrategia comercial equilibrada y monitorear conversion.")

        if night_share >= 0.4:
            recommendations.append("Aumentar precios en horario nocturno o lanzar tarifa premium.")
        if morning_share <= 0.2:
            recommendations.append("Promocionar la manana con paquetes empresariales y descuentos tempranos.")

        least_hour = self.least_requested_hour()
        if least_hour != "Sin datos":
            recommendations.append(
                f"Se recomienda aplicar promociones en el horario {least_hour} para activar demanda."
            )

        if pending_count >= max(2, total // 3):
            recommendations.append("Reforzar confirmaciones por WhatsApp para asegurar ingresos pendientes.")

        return recommendations[:4]

    def get_dashboard_metrics(self) -> dict:
        reservations = self._reservations()
        total_reservations = len(reservations)
        total_revenue = self.total_revenue()
        confirmed_statuses = {"confirmada", "PAID"}
        pending_statuses = {"pendiente", "PENDING_PAYMENT", "PARTIAL_PAYMENT"}
        confirmed_revenue = round(sum(float(item.total or 0.0) for item in reservations if item.status in confirmed_statuses), 2)
        pending_revenue = round(total_revenue - confirmed_revenue, 2)
        paid_reservations = [item for item in reservations if item.status == "PAID"]
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        month_start = today.replace(day=1)
        today_reservations = [item for item in reservations if item.reservation_date == today.isoformat()]
        week_reservations = [
            item
            for item in reservations
            if week_start <= date.fromisoformat(item.reservation_date) <= week_end
        ]
        month_reservations = [
            item
            for item in reservations
            if date.fromisoformat(item.reservation_date) >= month_start
            and date.fromisoformat(item.reservation_date).month == today.month
            and date.fromisoformat(item.reservation_date).year == today.year
        ]
        court_counts = Counter(item.service_type for item in reservations)
        top_court = court_counts.most_common(1)[0][0] if court_counts else "--"
        reservations_trend_counts = Counter(item.reservation_date for item in reservations)
        revenue_trend = {}
        for item in reservations:
            revenue_trend[item.reservation_date] = revenue_trend.get(item.reservation_date, 0.0) + float(item.total or 0.0)
        hour_counts = self._hour_counts()
        occupancy_available_slots = max(
            len({item.reservation_date for item in reservations} or {date.today().isoformat()})
            * len(SERVICE_TYPES)
            * len(TIME_OPTIONS),
            len(SERVICE_TYPES) * len(TIME_OPTIONS),
        )
        occupancy = self.occupancy_rate(occupancy_available_slots)
        insights = self.generate_insights()
        recommendations = self.generate_recommendations()
        peak_hour = self.most_requested_hour()
        peak_count = hour_counts.get(peak_hour, 0)

        sorted_hours = sorted(
            TIME_OPTIONS,
            key=lambda hour: (-hour_counts.get(hour, 0), hour),
        )
        sorted_low_hours = sorted(
            TIME_OPTIONS,
            key=lambda hour: (hour_counts.get(hour, 0), hour),
        )

        return {
            "total_reservations": total_reservations,
            "total_revenue": total_revenue,
            "confirmed_revenue": confirmed_revenue,
            "pending_revenue": pending_revenue,
            "revenue_today": round(sum(float(item.total or 0.0) for item in today_reservations), 2),
            "revenue_week": round(sum(float(item.total or 0.0) for item in week_reservations), 2),
            "confirmed_reservations": len([item for item in reservations if item.status in confirmed_statuses]),
            "pending_reservations": len([item for item in reservations if item.status in pending_statuses]),
            "paid_reservations": len(paid_reservations),
            "pending_payments": len([item for item in reservations if item.status in {"PENDING_PAYMENT", "PARTIAL_PAYMENT"}]),
            "failed_payments": len([item for item in reservations if item.status == "FAILED"]),
            "conversion_rate": round((len(paid_reservations) / total_reservations) * 100, 2) if total_reservations else 0.0,
            "most_profitable_court": top_court,
            "average_ticket": round(sum(float(item.total or 0.0) for item in paid_reservations) / len(paid_reservations), 2) if paid_reservations else 0.0,
            "peak_payment_hours": [],
            "top_court": top_court,
            "most_requested_hour": peak_hour,
            "least_requested_hour": self.least_requested_hour(),
            "top_hours": [(hour, hour_counts.get(hour, 0)) for hour in sorted_hours[:3]],
            "least_hours": [(hour, hour_counts.get(hour, 0)) for hour in sorted_low_hours[:3]],
            "peak_ranges": self.peak_ranges(),
            "reservations_by_hour": self.reservations_by_hour(),
            "reservations_trend": [
                {"date": key, "reservations": reservations_trend_counts[key]}
                for key in sorted(reservations_trend_counts)
            ],
            "revenue_trend": [
                {"date": key, "revenue": round(revenue_trend[key], 2)}
                for key in sorted(revenue_trend)
            ],
            "occupancy_rate": occupancy,
            "available_slots": occupancy_available_slots,
            "occupied_slots": self.total_reserved_hours(),
            "schedule_distribution": self.schedule_distribution(),
            "occupancy_heatmap": self.occupancy_heatmap(),
            "weekly_summary": {
                "start_date": week_start.isoformat(),
                "end_date": week_end.isoformat(),
                "reservations": len(week_reservations),
                "revenue": round(sum(float(item.total or 0.0) for item in week_reservations), 2),
            },
            "monthly_summary": {
                "start_date": month_start.isoformat(),
                "end_date": today.isoformat(),
                "reservations": len(month_reservations),
                "revenue": round(sum(float(item.total or 0.0) for item in month_reservations), 2),
            },
            "insights": insights,
            "recommendations": recommendations,
            "headline_insight": insights[0] if insights else "Operacion estable sin hallazgos destacados.",
            "primary_recommendation": (
                recommendations[0]
                if recommendations
                else "Mantener monitoreo diario del comportamiento de reservas."
            ),
            "kpis": {
                "total_reservations": self._reservation_status(total_reservations),
                "total_revenue": self._revenue_status(total_revenue),
                "occupancy_rate": self._occupancy_status(occupancy),
                "most_requested_hour": self._peak_hour_status(
                    peak_hour,
                    peak_count,
                    max(self.total_reserved_hours(), 1),
                ),
            },
        }
