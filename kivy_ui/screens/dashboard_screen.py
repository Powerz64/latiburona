from __future__ import annotations

from app.utils.formatters import format_currency
from kivy_ui.screens.base_screen import BaseScreen
from kivy_ui.theme import FIELD_IMAGES


DASHBOARD_FIELDS = (
    "La Jaula Barranquilla",
    "Brazuca Soccer",
    "Brasileirao",
    "La Castellana",
    "Soccer House",
)

COURT_LIVE_META = {
    "La Jaula Barranquilla": {
        "address": "Via 40 # 85-470",
        "location": "Riomar, Barranquilla",
        "reference": "Cerca de Viva Barranquilla",
        "access": "Acceso rápido desde Circunvalar",
        "court_type": "Futbol 5 premium",
        "promotion": "Promo madrugadores | 6AM-9AM -> 20% de descuento",
        "schedule": "Prime: 6AM-9AM | Luces nocturnas listas",
        "image_source": FIELD_IMAGES["la_jaula"],
        "badge": "Alta demanda",
        "status": "Lista",
        "tone": "success",
        "modifier": 0.18,
    },
    "Brazuca Soccer": {
        "address": "Calle 3 # 23-90",
        "location": "Villa Campestre",
        "reference": "Ruta universitaria y acceso norte",
        "access": "Parqueo junto a entrada principal",
        "court_type": "Sintética 7v7",
        "promotion": "Liga universitaria | 5+ jugadores -> bebidas gratis",
        "schedule": "Bloques posjornada con alta rotación",
        "image_source": FIELD_IMAGES["brazuca"],
        "badge": "Disponible",
        "status": "Cupos activos",
        "tone": "primary",
        "modifier": 0.04,
    },
    "Brasileirao": {
        "address": "Carrera 46 # 76-109",
        "location": "Norte Centro Historico",
        "reference": "A 8 minutos del Romelio Martínez",
        "access": "Entrada principal sobre Carrera 46",
        "court_type": "Futbol 5 grama tech",
        "promotion": "Noche Prime | Despues de 8PM -> balon incluido",
        "schedule": "Cancha top nocturna | 8PM-10PM",
        "image_source": FIELD_IMAGES["brasileirao"],
        "badge": "Modo nocturno",
        "status": "Top noche",
        "tone": "success",
        "modifier": 0.11,
    },
    "La Castellana": {
        "address": "Carrera 53 # 94-160",
        "location": "La Castellana",
        "reference": "Cerca de Buenavista y Viva",
        "access": "Entrada familiar con parqueo fácil",
        "court_type": "Cancha familiar",
        "promotion": "Fin de semana familiar | Niños entran gratis los domingos",
        "schedule": "Cupos familiares protegidos en fin de semana",
        "image_source": FIELD_IMAGES["castellana"],
        "badge": "Top noche",
        "status": "Lista",
        "tone": "primary",
        "modifier": -0.03,
    },
    "Soccer House": {
        "address": "Calle 25 # 3-126",
        "location": "Suroriente",
        "reference": "Ruta rápida desde Murillo",
        "access": "Descenso rápido junto a la entrada",
        "court_type": "Cancha comunitaria",
        "promotion": "Reto de martes | 2 horas por precio de 1.5",
        "schedule": "Desafio destacado: martes",
        "image_source": FIELD_IMAGES["soccer_house"],
        "badge": "Promo activa",
        "status": "Disponible",
        "tone": "success",
        "modifier": -0.12,
    },
}


class DashboardScreen(BaseScreen):
    def on_kv_post(self, *_args) -> None:
        super().on_kv_post(*_args)
        self._prime_cards()

    def fetch_data(self) -> dict:
        return self.get_service("analytics_service").get_dashboard_metrics()

    def apply_data(self, payload: dict) -> None:
        revenue = float(payload.get("total_revenue", 0) or 0)
        revenue_today = float(payload.get("revenue_today", revenue) or 0)
        revenue_week = float(payload.get("revenue_week", revenue) or 0)
        reservations = int(payload.get("total_reservations", 0) or 0)
        confirmed_reservations = int(payload.get("confirmed_reservations", 0) or 0)
        pending_reservations = int(payload.get("pending_reservations", 0) or 0)
        paid_reservations = int(payload.get("paid_reservations", 0) or 0)
        pending_payments = int(payload.get("pending_payments", 0) or 0)
        failed_payments = int(payload.get("failed_payments", 0) or 0)
        conversion_rate = float(payload.get("conversion_rate", 0) or 0)
        average_ticket = float(payload.get("average_ticket", 0) or 0)
        occupancy = float(payload.get("occupancy_rate", 0) or 0)
        peak_hour = str(payload.get("most_requested_hour") or "--")
        top_court = str(payload.get("top_court") or "--")
        most_profitable_court = str(payload.get("most_profitable_court") or top_court or "--")
        reservations_by_hour = dict(payload.get("reservations_by_hour") or {})
        insights = list(payload.get("insights") or [])
        recommendations = list(payload.get("recommendations") or [])
        live_rows = self._build_live_occupancy_rows(occupancy, reservations_by_hour, reservations, peak_hour)
        live_courts = self._build_live_court_cards(occupancy, reservations, peak_hour)

        self.ids.revenue_card.set_data(
            {
                "title": "💰 Ingresos cancha",
                "value": format_currency(revenue_today),
                "status": "Hoy",
                "tone": "success" if revenue_today > 0 else "primary",
                "caption": f"Semana: {format_currency(revenue_week)} | Total: {format_currency(revenue)}",
            }
        )
        self.ids.total_reservations_card.set_data(
            {
                "title": "📅 Partidos",
                "value": str(reservations),
                "status": "Agenda",
                "tone": "primary",
                "caption": f"Confirmadas: {confirmed_reservations} | Pendientes: {pending_reservations}",
            }
        )
        self.ids.occupancy_card.set_data(
            {
                "title": "🏟 Ocupacion",
                "value": f"{occupancy:.1f}%",
                "status": "Uso cancha",
                "tone": "success" if occupancy >= 70 else "warning" if occupancy >= 40 else "danger",
                "caption": "Porcentaje de uso sobre la agenda disponible.",
            }
        )
        self.ids.peak_hour_card.set_data(
            {
                "title": "💡 Hora pico",
                "value": peak_hour,
                "status": top_court,
                "tone": "primary" if peak_hour != "Sin datos" else "warning",
                "caption": "Franja con mayor demanda y cancha lider.",
            }
        )
        self.ids.demand_card.set_data(
            {
                "peak_label": peak_hour if peak_hour != "Sin datos" else "",
                "peak_text": f"Hora pico de cancha: {peak_hour}",
                "chart_data": reservations_by_hour,
                "summary": (
                    f"Total partidos: {reservations} | Ocupacion: {occupancy:.1f}%"
                    if reservations
                    else "Aun no hay reservas suficientes para leer la demanda deportiva."
                ),
            }
        )
        self.ids.live_occupancy_card.set_data(
            {
                "title": "Ocupacion live de canchas",
                "subtitle": "Lectura operativa: demanda, cupos y ritmo por sede.",
                "rows": live_rows,
            }
        )
        self._apply_live_court_cards(live_courts)
        self._apply_mini_widgets(
            reservations,
            occupancy,
            peak_hour,
            live_courts,
            paid_reservations=paid_reservations,
            pending_payments=pending_payments,
            failed_payments=failed_payments,
            conversion_rate=conversion_rate,
            average_ticket=average_ticket,
            most_profitable_court=most_profitable_court,
        )
        self.ids.insights_card.apply_data(
            "Lectura deportiva",
            "\n".join(f"- {item}" for item in insights[:3]) or "- Sin insights disponibles.",
            eyebrow="Analitica de cancha",
            badge="Lectura",
            icon="⚽",
            tone="primary",
        )
        self.ids.recommendations_card.apply_data(
            "Jugadas recomendadas",
            "\n".join(f"- {item}" for item in recommendations[:3]) or "- Sin recomendaciones disponibles.",
            eyebrow="Plan operativo",
            badge="Prioridad",
            icon="🏆",
            tone="success" if reservations else "warning",
            highlighted=True,
        )
        self.set_status("Tablero deportivo actualizado con datos en tiempo real.")

    def apply_error(self, error: Exception) -> None:
        self.ids.revenue_card.set_error("No fue posible leer ingresos.")
        self.ids.total_reservations_card.set_error("No fue posible leer reservas.")
        self.ids.occupancy_card.set_error("No fue posible leer ocupacion.")
        self.ids.peak_hour_card.set_error("No fue posible detectar la hora pico.")
        self.ids.demand_card.set_error("No fue posible construir la demanda por hora.")
        self.ids.live_occupancy_card.set_error("No fue posible leer ocupacion live.")
        for index in range(1, 6):
            card_id = f"field_card_{index}"
            if card_id in self.ids:
                self.ids[card_id].set_error("Sin lectura live")
        for card_id in (
            "mini_peak_card",
            "mini_today_card",
            "mini_night_card",
            "mini_tournament_card",
            "mini_average_card",
            "mini_featured_card",
        ):
            if card_id in self.ids:
                self.ids[card_id].set_error("Sin datos")
        self.ids.insights_card.set_error("No fue posible generar insights.")
        self.ids.recommendations_card.set_error("No fue posible generar recomendaciones.")
        self.set_status(f"Error al cargar dashboard: {error}")

    def _build_live_court_cards(self, occupancy: float, reservation_count: int, peak_hour: str) -> list[dict]:
        base_ratio = max(0.0, min(float(occupancy or 0) / 100, 1.0))
        if reservation_count <= 0:
            base_ratio = 0.28
        peak_label = peak_hour if peak_hour and peak_hour != "Sin datos" else "Sin pico aun"
        cards = []
        for field_name in DASHBOARD_FIELDS:
            meta = COURT_LIVE_META[field_name]
            ratio = max(0.12, min(base_ratio + float(meta["modifier"]), 0.98))
            free_slots = max(0, round((1 - ratio) * 10))
            if ratio >= 0.9:
                badge = "Completa"
                tone = "danger"
            elif ratio >= 0.75:
                badge = str(meta["badge"])
                tone = str(meta["tone"])
            elif ratio >= 0.45:
                badge = str(meta["status"])
                tone = str(meta["tone"])
            else:
                badge = "Disponible"
                tone = "primary"
            cards.append(
                {
                    "field_name": field_name,
                    "address": meta["address"],
                    "location": meta["location"],
                    "availability": badge,
                    "live_status": "EN VIVO",
                    "occupancy": f"{round(ratio * 100)}% ocupación",
                    "slots": f"{free_slots} cupos disponibles | Hora pico {peak_label}",
                    "court_type": meta["court_type"],
                    "reference": meta["reference"],
                    "access": meta["access"],
                    "promotion": meta["promotion"],
                    "schedule": meta["schedule"],
                    "occupancy_ratio": ratio,
                    "image_source": meta["image_source"],
                    "tone": tone,
                }
            )
        return cards

    def _apply_live_court_cards(self, cards: list[dict]) -> None:
        for index, card_data in enumerate(cards, start=1):
            card_id = f"field_card_{index}"
            if card_id in self.ids:
                self.ids[card_id].set_data(card_data)

    def _apply_mini_widgets(
        self,
        reservations: int,
        occupancy: float,
        peak_hour: str,
        live_courts: list[dict],
        *,
        paid_reservations: int = 0,
        pending_payments: int = 0,
        failed_payments: int = 0,
        conversion_rate: float = 0.0,
        average_ticket: float = 0.0,
        most_profitable_court: str = "--",
    ) -> None:
        top_court = max(live_courts, key=lambda item: item.get("occupancy_ratio", 0), default={})
        featured = live_courts[0] if live_courts else {}
        self.ids.mini_peak_card.set_data(
            {
                "title": "Hora pico",
                "value": peak_hour if peak_hour != "Sin datos" else "--",
                "status": "Demanda en vivo",
                "tone": "primary",
                "caption": "Franja mas activa del dia.",
            }
        )
        self.ids.mini_today_card.set_data(
            {
                "title": "Reservas de hoy",
                "value": str(reservations),
                "status": "Agenda",
                "tone": "success" if reservations else "warning",
                "caption": "Partidos registrados en operacion.",
            }
        )
        self.ids.mini_night_card.set_data(
            {
                "title": "Cancha top noche",
                "value": top_court.get("field_name", "--").replace(" Barranquilla", ""),
                "status": top_court.get("availability", "Noche"),
                "tone": top_court.get("tone", "primary"),
                "caption": top_court.get("schedule", "Cupos nocturnos listos."),
            }
        )
        self.ids.mini_tournament_card.set_data(
            {
                "title": "Pagos pendientes",
                "value": str(pending_payments),
                "status": "Checkout",
                "tone": "warning" if pending_payments else "success",
                "caption": f"Fallidos: {failed_payments} | Conversion {conversion_rate:.1f}%",
            }
        )
        self.ids.mini_average_card.set_data(
            {
                "title": "Ticket promedio",
                "value": format_currency(average_ticket),
                "status": f"{paid_reservations} pagadas",
                "tone": "success" if paid_reservations else "warning",
                "caption": "Promedio de pagos aprobados.",
            }
        )
        self.ids.mini_featured_card.set_data(
            {
                "title": "Cancha mas rentable",
                "value": most_profitable_court.replace(" Barranquilla", ""),
                "status": "Ingreso pago",
                "tone": featured.get("tone", "success"),
                "caption": "Ordenada por pagos confirmados.",
            }
        )

    def _build_live_occupancy_rows(
        self,
        occupancy: float,
        reservations_by_hour: dict,
        reservation_count: int,
        peak_hour: str,
    ) -> list[dict]:
        base_ratio = max(0.0, min(float(occupancy or 0) / 100, 1.0))
        if reservation_count <= 0:
            base_ratio = 0.18
        modifiers = (0.18, 0.04, 0.11, -0.03, -0.12)
        peak_label = peak_hour if peak_hour and peak_hour != "Sin datos" else "Sin pico"
        rows = []
        for index, field_name in enumerate(DASHBOARD_FIELDS):
            ratio = max(0.08, min(base_ratio + modifiers[index], 0.96))
            free_slots = max(1, round((1 - ratio) * 10))
            if ratio >= 0.78:
                status_text = "Alta demanda"
                tone = "success"
            elif ratio >= 0.58:
                status_text = "Ritmo fuerte"
                tone = "primary"
            elif ratio >= 0.36:
                status_text = "Disponible"
                tone = "warning"
            else:
                status_text = "Libre"
                tone = "neutral"
            rows.append(
                {
                    "field_name": field_name,
                    "status_text": f"{round(ratio * 100)}% {status_text}",
                    "slot_text": f"{free_slots} cupos libres | Hora pico {peak_label}",
                    "occupancy_ratio": ratio,
                    "tone": tone,
                }
            )
        return rows

    def _prime_cards(self) -> None:
        self.ids.revenue_card.set_loading(
            {
                "title": "💰 Ingresos cancha",
                "caption": "Sincronizando caja de partidos...",
                "tone": "primary",
            }
        )
        self.ids.total_reservations_card.set_loading(
            {
                "title": "📅 Partidos",
                "caption": "Contando reservas activas...",
                "tone": "primary",
            }
        )
        self.ids.occupancy_card.set_loading(
            {
                "title": "🏟 Ocupacion",
                "caption": "Midiendo uso de canchas...",
                "tone": "primary",
            }
        )
        self.ids.peak_hour_card.set_loading(
            {
                "title": "💡 Hora pico",
                "caption": "Buscando la franja con mas juego...",
                "tone": "primary",
            }
        )
        self.ids.demand_card.set_loading({"peak_text": "Hora pico de cancha: --"})
        self.ids.live_occupancy_card.set_loading(
            {
                "title": "Ocupacion live de canchas",
                "subtitle": "Sincronizando ritmo de sedes y cupos disponibles...",
            }
        )
        for index in range(1, 6):
            card_id = f"field_card_{index}"
            if card_id in self.ids:
                self.ids[card_id].set_loading()
        for card_id in (
            "mini_peak_card",
            "mini_today_card",
            "mini_night_card",
            "mini_tournament_card",
            "mini_average_card",
            "mini_featured_card",
        ):
            if card_id in self.ids:
                self.ids[card_id].set_loading({"title": "Widget operativo", "caption": "Sincronizando operacion..."})
        self.ids.insights_card.set_loading(
            {
                "title": "Lectura deportiva",
                "body": "Preparando lectura de cancha...",
                "eyebrow": "Analitica de cancha",
                "badge": "Cargando",
                "icon": "⚽",
                "tone": "primary",
            }
        )
        self.ids.recommendations_card.set_loading(
            {
                "title": "Jugadas recomendadas",
                "body": "Preparando plan operativo...",
                "eyebrow": "Prioridad deportiva",
                "badge": "Cargando",
                "icon": "🏆",
                "tone": "warning",
                "highlighted": True,
            }
        )
