from __future__ import annotations

import unicodedata
import webbrowser
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone

from kivy.app import App
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup

from app.services import ReservationConflictValidationError
from app.utils.constants import END_TIME_OPTIONS, SERVICE_TYPES, TIME_OPTIONS
from app.utils.formatters import format_currency, format_date, format_reservation_window
from app.utils.validators import ValidationError
from kivy_ui.components.cards import ReservationCourtCard
from kivy_ui.components.buttons import PrimaryButton, SecondaryButton
from kivy_ui.components.rows import ReservationRow
from kivy_ui.screens.base_screen import ServiceScreen
from kivy_ui.theme import FIELD_IMAGES, UI_FONT, active_theme_hex, rgba


FIELDS = {
    "La Jaula Barranquilla": "Via 40 # 85-470",
    "Brazuca Soccer": "Calle 3 # 23-90",
    "Brasileirao": "Carrera 46 # 76-109",
    "La Castellana": "Carrera 53 # 94-160",
    "Soccer House": "Calle 25 # 3-126",
}
FIELD_NAMES = list(FIELDS.keys())
FIELD_SERVICE_TYPES = {
    "La Jaula Barranquilla": "Cancha multiple",
    "Brazuca Soccer": "Zona recreativa",
    "Brasileirao": "Cancha sintetica",
    "La Castellana": "Cancha multiple",
    "Soccer House": "Piscina",
}
DEFAULT_FIELD_BY_SERVICE_TYPE = {
    "Cancha multiple": "La Jaula Barranquilla",
    "Zona recreativa": "Brazuca Soccer",
    "Cancha sintetica": "Brasileirao",
    "Piscina": "Soccer House",
}
FIELD_CARD_META = {
    "La Jaula Barranquilla": {
        "location": "Riomar",
        "court_type": "Futbol 5 premium",
        "promotion": "Promo madrugadores",
        "features": "LED incluido | Parqueadero",
        "peak": "Pico 7PM",
        "image_source": FIELD_IMAGES["la_jaula"],
        "tone": "success",
        "base": 0.78,
    },
    "Brazuca Soccer": {
        "location": "Villa Campestre",
        "court_type": "Sintetica 7v7",
        "promotion": "Liga universitaria",
        "features": "Zona cubierta | Acceso norte",
        "peak": "Pico 6PM",
        "image_source": FIELD_IMAGES["brazuca"],
        "tone": "primary",
        "base": 0.54,
    },
    "Brasileirao": {
        "location": "Norte Centro Historico",
        "court_type": "Grama tech",
        "promotion": "Promo nocturna",
        "features": "LED incluido | Balon gratis",
        "peak": "Pico 8PM",
        "image_source": FIELD_IMAGES["brasileirao"],
        "tone": "success",
        "base": 0.68,
    },
    "La Castellana": {
        "location": "La Castellana",
        "court_type": "Cancha familiar",
        "promotion": "Fin de semana familiar",
        "features": "Parqueadero | Acceso rapido",
        "peak": "Pico 5PM",
        "image_source": FIELD_IMAGES["castellana"],
        "tone": "primary",
        "base": 0.48,
    },
    "Soccer House": {
        "location": "Suroriente",
        "court_type": "Cancha comunitaria",
        "promotion": "Reto de martes",
        "features": "Zona cubierta | Ruta Murillo",
        "peak": "Pico 9PM",
        "image_source": FIELD_IMAGES["soccer_house"],
        "tone": "success",
        "base": 0.36,
    },
}
FIELD_ALIASES = {
    "Brazuca Soccer (Villa Campestre)": "Brazuca Soccer",
    "Cancha Sintética Brasileirao": "Brasileirao",
    "Cancha La Castellana": "La Castellana",
    "Soccer House Barranquilla": "Soccer House",
}


def _normalize_field_value(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in normalized if not unicodedata.combining(char)).strip().casefold()


ADDRESS_TO_FIELD = {_normalize_field_value(address): field_name for field_name, address in FIELDS.items()}
NORMALIZED_FIELD_NAMES = {_normalize_field_value(field_name): field_name for field_name in FIELD_NAMES}
NORMALIZED_FIELD_NAMES.update(
    {_normalize_field_value(alias): field_name for alias, field_name in FIELD_ALIASES.items()}
)


def field_backend_type(field_name: str) -> str:
    return FIELD_SERVICE_TYPES.get(field_name, SERVICE_TYPES[0])


def field_address_for(field_name: str, fallback: str = "") -> str:
    return FIELDS.get(field_name, fallback)


def resolve_field_name(service_type: str, address: str = "") -> str:
    normalized_address = _normalize_field_value(address)
    if normalized_address in ADDRESS_TO_FIELD:
        return ADDRESS_TO_FIELD[normalized_address]
    normalized_service = (service_type or "").strip()
    normalized_service_key = _normalize_field_value(normalized_service)
    if normalized_service in FIELDS:
        return normalized_service
    if normalized_service_key in NORMALIZED_FIELD_NAMES:
        return NORMALIZED_FIELD_NAMES[normalized_service_key]
    if normalized_service in DEFAULT_FIELD_BY_SERVICE_TYPE:
        return DEFAULT_FIELD_BY_SERVICE_TYPE[normalized_service]
    return FIELD_NAMES[0]


def _display_schedule_label(value: str) -> str:
    return "Mañana" if str(value or "").strip() == "Manana" else value


PAYMENT_STATUS_LABELS = {
    "pending": "Pago pendiente",
    "paid": "Pagada",
    "failed": "Pago fallido",
    "refunded": "Reembolsada",
    "cancelled": "Pago cancelado",
}

RESERVATION_STATUS_LABELS = {
    "draft": "Borrador",
    "pending_payment": "Pago pendiente",
    "confirmed": "Confirmada",
    "paid": "Pagada",
    "failed": "Fallida",
    "cancelled": "Cancelada",
    "refunded": "Reembolsada",
    "expired": "Expirada",
    "pendiente": "Pendiente",
    "confirmada": "Confirmada",
    "cancelada": "Cancelada",
    "PENDING_PAYMENT": "Pago pendiente",
    "PARTIAL_PAYMENT": "Pago parcial",
    "PAID": "Pagada",
    "FAILED": "Fallida",
    "CANCELLED": "Cancelada",
    "REFUNDED": "Reembolsada",
    "EXPIRED": "Expirada",
}

WEEKDAY_SHORT_LABELS = ["L", "M", "M", "J", "V", "S", "D"]
MONTH_LABELS = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]


class ReservationDatePicker(Popup):
    def __init__(self, selected_date: str, on_select, **kwargs) -> None:
        theme = active_theme_hex()
        self.on_select = on_select
        self.current_month = self._parse_date(selected_date)
        super().__init__(
            title="Seleccionar fecha",
            title_align="left",
            title_font=UI_FONT,
            title_color=rgba(theme["text_primary"]),
            separator_color=rgba(theme["primary"]),
            size_hint=(None, None),
            size=(dp(430), dp(488)),
            auto_dismiss=True,
            **kwargs,
        )
        self.background_color = rgba(theme["surface"])
        self._content = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(12))
        self.content = self._content
        self._render()

    @staticmethod
    def _parse_date(value: str) -> date:
        try:
            return date.fromisoformat(str(value or "").strip())
        except ValueError:
            return date.today()

    def _render(self) -> None:
        theme = active_theme_hex()
        self._content.clear_widgets()
        header = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(10))
        prev_button = SecondaryButton(text="<", size_hint_x=None, width=dp(48))
        next_button = SecondaryButton(text=">", size_hint_x=None, width=dp(48))
        month_label = Label(
            text=f"{MONTH_LABELS[self.current_month.month - 1].capitalize()} {self.current_month.year}",
            font_name=UI_FONT,
            color=rgba(theme["text_primary"]),
            bold=True,
            font_size="18sp",
            text_size=(dp(250), dp(44)),
            halign="center",
            valign="middle",
        )
        prev_button.bind(on_release=lambda *_args: self._shift_month(-1))
        next_button.bind(on_release=lambda *_args: self._shift_month(1))
        header.add_widget(prev_button)
        header.add_widget(month_label)
        header.add_widget(next_button)
        self._content.add_widget(header)

        quick = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        for label, target in (
            ("Hoy", date.today()),
            ("Mañana", date.today() + timedelta(days=1)),
            ("Fin de semana", self._next_weekend()),
        ):
            button = SecondaryButton(text=label)
            button.bind(on_release=lambda _btn, selected=target: self._select(selected))
            quick.add_widget(button)
        self._content.add_widget(quick)

        weekdays = GridLayout(cols=7, size_hint_y=None, height=dp(24), spacing=dp(4))
        for label in WEEKDAY_SHORT_LABELS:
            weekdays.add_widget(
                Label(
                    text=label,
                    font_name=UI_FONT,
                    color=rgba(theme["text_muted"]),
                    font_size="12sp",
                    bold=True,
                    text_size=(dp(44), dp(24)),
                    halign="center",
                    valign="middle",
                )
            )
        self._content.add_widget(weekdays)

        days_grid = GridLayout(cols=7, size_hint_y=None, height=dp(252), spacing=dp(6))
        first_day = self.current_month.replace(day=1)
        _, days_in_month = monthrange(first_day.year, first_day.month)
        offset = first_day.weekday()
        for _ in range(offset):
            days_grid.add_widget(Label(text=""))
        for day in range(1, days_in_month + 1):
            current = first_day.replace(day=day)
            is_today = current == date.today()
            button = PrimaryButton(text=str(day)) if is_today else SecondaryButton(text=str(day))
            button.size_hint_y = None
            button.height = dp(36)
            button.bind(on_release=lambda _btn, selected=current: self._select(selected))
            days_grid.add_widget(button)
        for _ in range(max(0, 42 - offset - days_in_month)):
            days_grid.add_widget(Label(text=""))
        self._content.add_widget(days_grid)

        close_button = SecondaryButton(text="Cerrar", size_hint_y=None, height=dp(42))
        close_button.bind(on_release=lambda *_args: self.dismiss())
        self._content.add_widget(close_button)

    @staticmethod
    def _next_weekend() -> date:
        today = date.today()
        days_until_saturday = (5 - today.weekday()) % 7
        return today + timedelta(days=days_until_saturday)

    def _shift_month(self, direction: int) -> None:
        month = self.current_month.month + direction
        year = self.current_month.year
        if month < 1:
            month = 12
            year -= 1
        elif month > 12:
            month = 1
            year += 1
        self.current_month = self.current_month.replace(year=year, month=month, day=1)
        self._render()

    def _select(self, selected: date) -> None:
        self.dismiss()
        if self.on_select:
            self.on_select(selected.isoformat())


class ReservationsScreen(ServiceScreen):
    service_options = ListProperty(FIELD_NAMES)
    start_time_options = ListProperty(TIME_OPTIONS)
    end_time_options = ListProperty(END_TIME_OPTIONS)
    form_heading = StringProperty("Nuevo partido")
    save_button_text = StringProperty("Guardar partido")
    summary_text = StringProperty("No hay partidos registrados todavia.")
    current_status = StringProperty("pendiente")
    current_reservation_id = NumericProperty(0)
    has_reservations = BooleanProperty(False)
    reservations_data = ListProperty([])
    empty_state_text = StringProperty("No hay partidos registrados todavia.")
    quote_schedule_text = StringProperty("Esperando datos para cotizar")
    quote_total_text = StringProperty("$0 COP")
    quote_discount_text = StringProperty("Descuento aplicado: 0%")
    quote_promotion_text = StringProperty("Promociones: Sin promociones")
    quote_support_text = StringProperty("Completa fecha, rango y personas para obtener la cotizacion.")
    availability_text = StringProperty("Selecciona fecha, cancha y rango para validar disponibilidad.")
    availability_color = StringProperty("neutral")
    selected_range_text = StringProperty("Sin rango seleccionado")
    save_feedback_text = StringProperty("")
    save_feedback_tone = StringProperty("neutral")
    selected_court_name = StringProperty(FIELD_NAMES[0])
    live_court_summary_text = StringProperty("Selecciona una cancha para completar el formulario.")
    live_courts_data = ListProperty([])
    smart_suggestion_text = StringProperty("Sugerencia inteligente: selecciona fecha, hora y cancha.")
    smart_pricing_text = StringProperty("Precio inteligente listo para previsualizar.")
    activity_feed_data = ListProperty([])

    def __init__(self, **kwargs) -> None:
        self._suspend_form_events = True
        super().__init__(**kwargs)
        self._suspend_form_events = False

    def on_kv_post(self, *_args) -> None:
        super().on_kv_post(*_args)
        self._suspend_form_events = True
        try:
            self.bind(size=self._update_layout)
            self.ids.date_input.bind(text=lambda *_args: self._handle_form_change())
            self.ids.service_spinner.bind(text=lambda *_args: self._handle_form_change())
            self.ids.start_time_spinner.bind(text=lambda *_args: self._handle_start_time_change())
            self.ids.end_time_spinner.bind(text=lambda *_args: self._handle_form_change())
            self.ids.people_input.bind(text=lambda *_args: self.update_quote())
            self._set_service_options(list(FIELD_NAMES))
            self.ids.date_input.text = date.today().isoformat()
            self.on_field_selected(self.ids.service_spinner.text)
            self._update_layout()
            self._reset_quote_preview()
            self._render_live_courts()
            self.activity_feed_data = self._build_activity_feed([])
            self._render_activity_feed()
        finally:
            self._suspend_form_events = False

    def _update_layout(self, *_args) -> None:
        if not self.ids:
            return
        self.ids.content_grid.cols = 1 if self.width < dp(1180) else 2
        self.ids.form_grid.cols = 1 if self.width < dp(1160) else 2
        if "live_courts_grid" in self.ids:
            self.ids.live_courts_grid.cols = 1 if self.width < dp(720) else 2

    def refresh(self) -> None:
        self.set_status("Cargando reservas...")
        self.load_data(
            "reservations_refresh",
            self._fetch_reservations_data,
            self._apply_reservations_data,
            self._handle_reservations_error,
            cache_name="reservas",
            loading_message="Cargando reservas y disponibilidad...",
        )

    def _fetch_reservations_data(self) -> dict:
        remote_mode = self.get_service("sync_mode") == "remote"
        api_client = self.get_service("api_client")
        can_manage_actions = self._can_manage_reservations()

        service_options = list(FIELD_NAMES)
        reservations = self.get_service("reservation_service").get_all_reservations()
        pricing_service = self.get_service("pricing_service")
        confirmed_count = len([item for item in reservations if item.status in {"confirmada", "PAID", "confirmed", "paid"}])

        reservations_payload = []
        for reservation in reservations:
            field_name = resolve_field_name(reservation.service_type, reservation.address)
            pricing = pricing_service.calculate_price(
                reservation.reservation_date,
                reservation.start_time,
                reservation.people_count,
                reservation.end_time,
            )
            promotions = self._format_reservation_promotions(pricing)
            discount_text = (
                f"Group promo: -{pricing.bulk_discount_percent:.0f}%"
                if pricing.bulk_discount_percent
                else ""
            )
            promo_label = self._format_promo_label(pricing)
            match_badge = self._match_badge_for(
                reservation.status,
                reservation.schedule,
                reservation.people_count,
            )
            payment_status = str(reservation.payment_status or "").strip().lower()
            payment_tone = self._payment_tone(payment_status, reservation.status)
            reservations_payload.append(
                {
                    "reservation_id": reservation.id or 0,
                    "data": {
                        "reservation_id": reservation.id or 0,
                        "field_name": field_name,
                        "service_type": reservation.service_type,
                        "address": reservation.address,
                        "status": reservation.status,
                        "payment_status": payment_status,
                    },
                    "client_name": reservation.client_name,
                    "service_type": field_name,
                    "datetime_text": (
                        f"{format_date(reservation.reservation_date)} | "
                        f"{format_reservation_window(reservation.start_time, reservation.end_time)}"
                    ),
                    "people_text": f"{reservation.people_count} personas",
                    "schedule_text": _display_schedule_label(reservation.schedule),
                    "status_text": RESERVATION_STATUS_LABELS.get(reservation.status, reservation.status.title()),
                    "status_tone": "success" if reservation.status in {"confirmada", "PAID", "confirmed", "paid"} else "danger" if reservation.status in {"FAILED", "CANCELLED", "REFUNDED", "EXPIRED", "cancelada", "failed", "cancelled", "refunded", "expired"} else "warning",
                    "payment_status_text": PAYMENT_STATUS_LABELS.get(payment_status, "Pago por confirmar"),
                    "payment_tone": payment_tone,
                    "expiration_text": self._expiration_text(reservation.payment_expires_at, reservation.status),
                    "promotion_text": promotions,
                    "discount_text": discount_text,
                    "promo_label_text": promo_label,
                    "match_badge_text": match_badge,
                    "total_text": format_currency(reservation.total),
                    "is_confirmed": reservation.status in {"confirmada", "PAID", "confirmed", "paid"},
                    "show_management_actions": can_manage_actions,
                }
            )

        payload = {
            "service_options": service_options,
            "has_reservations": bool(reservations),
            "summary_text": (
                f"{len(reservations)} partidos registrados | {confirmed_count} confirmados | "
                f"{len(reservations) - confirmed_count} pendientes"
                if reservations
                else "No hay partidos registrados todavia."
            ),
            "reservations_data": reservations_payload,
            "live_courts_data": self._build_live_courts_payload(reservations),
            "activity_feed_data": self._build_activity_feed(reservations),
            "empty_state_text": (
                "No hay partidos registrados todavia. Crea el primero desde el formulario."
                if not reservations
                else ""
            ),
            "offline_mode": False,
        }

        if remote_mode and api_client.last_error == "network_error":
            raise RuntimeError("network_error")
        return payload

    def _apply_reservations_data(self, payload: dict) -> None:
        self._suspend_form_events = True
        try:
            self._set_service_options(payload["service_options"])
            self.has_reservations = payload["has_reservations"]
            self.summary_text = (
                f"{payload['summary_text']} | Modo offline"
                if payload.get("offline_mode")
                else payload["summary_text"]
            )
            self.reservations_data = list(payload["reservations_data"])
            self.live_courts_data = list(payload.get("live_courts_data", []))
            self.activity_feed_data = list(payload.get("activity_feed_data", []))
            self.empty_state_text = payload["empty_state_text"]
        finally:
            self._suspend_form_events = False
        self._render_reservations()
        self._render_live_courts()
        self._render_activity_feed()
        self.update_quote()
        self._request_availability_refresh(show_loading=False)
        self.set_status(
            "Modo offline: mostrando la ultima copia de reservas."
            if payload.get("offline_mode")
            else "Reservas sincronizadas en el tablero deportivo."
        )

    def _handle_reservations_error(self, error: Exception) -> None:
        self.has_reservations = bool(self.reservations_data)
        self.summary_text = "No fue posible cargar las reservas."
        self.empty_state_text = "Intenta nuevamente en unos segundos."
        self.availability_text = "No fue posible consultar disponibilidad."
        self.availability_color = "danger"
        self._render_reservations()
        self._render_live_courts()
        self._render_activity_feed()
        self.set_status(f"Error al cargar reservas: {error}")

    def _render_reservations(self) -> None:
        if not self.ids or "reservations_list" not in self.ids:
            return
        container = self.ids.reservations_list
        container.clear_widgets()
        can_manage_actions = self._can_manage_reservations()
        for item in self.reservations_data:
            row_data = dict(item)
            row_data["schedule_text"] = _display_schedule_label(row_data.get("schedule_text", ""))
            row_data["show_management_actions"] = can_manage_actions
            container.add_widget(ReservationRow(**row_data))

    def _build_activity_feed(self, reservations: list) -> list[dict]:
        items = []
        sorted_items = sorted(
            reservations,
            key=lambda item: str(item.created_at or ""),
            reverse=True,
        )[:6]
        for item in sorted_items:
            field_name = resolve_field_name(item.service_type, item.address)
            status_label = RESERVATION_STATUS_LABELS.get(item.status, str(item.status or "").title())
            payment_label = PAYMENT_STATUS_LABELS.get(str(item.payment_status or "").lower(), "Pago por confirmar")
            tone = "success" if item.status in {"confirmada", "PAID", "confirmed", "paid"} else "danger" if item.status in {"failed", "cancelled", "expired", "refunded", "FAILED", "CANCELLED", "EXPIRED", "REFUNDED"} else "warning"
            items.append(
                {
                    "title": f"{status_label} | {field_name}",
                    "detail": f"{item.client_name} | {item.start_time}-{item.end_time} | {payment_label}",
                    "tone": tone,
                }
            )
        if not items:
            items.append(
                {
                    "title": "Operacion lista",
                    "detail": "Crea una reserva para activar el feed en vivo.",
                    "tone": "primary",
                }
            )
        return items

    def _render_activity_feed(self) -> None:
        if not self.ids or "activity_feed_list" not in self.ids:
            return
        theme = active_theme_hex()
        container = self.ids.activity_feed_list
        container.clear_widgets()
        for item in self.activity_feed_data[:6]:
            color_key = "success" if item.get("tone") == "success" else "danger" if item.get("tone") == "danger" else "primary"
            container.add_widget(
                Label(
                    text=f"[b]{item.get('title', '')}[/b]\n{item.get('detail', '')}",
                    markup=True,
                    font_name=UI_FONT,
                    color=rgba(theme[color_key]),
                    font_size="12sp",
                    size_hint_y=None,
                    height=dp(42),
                    text_size=(container.width, None),
                    halign="left",
                    valign="top",
                    shorten=True,
                    shorten_from="right",
                )
            )

    def _set_service_options(self, options: list[str]) -> None:
        resolved_options = list(FIELD_NAMES)
        self.service_options = resolved_options
        if not self.ids:
            return
        current_value = self.ids.service_spinner.text.strip()
        self._suspend_form_events = True
        try:
            self.ids.service_spinner.text = (
                current_value if current_value in resolved_options else resolved_options[0]
            )
        finally:
            self._suspend_form_events = False
        self.on_field_selected(self.ids.service_spinner.text)

    def _build_live_courts_payload(self, reservations: list) -> list[dict]:
        selected = self.selected_court_name or self._selected_field_name()
        items = []
        for index, field_name in enumerate(FIELD_NAMES):
            meta = FIELD_CARD_META[field_name]
            active_reservations = [
                item for item in reservations
                if resolve_field_name(item.service_type, item.address) == field_name
                and item.status not in {"cancelada", "CANCELLED", "FAILED", "REFUNDED", "EXPIRED"}
            ]
            ratio = max(0.08, min(0.96, float(meta["base"]) + (len(active_reservations) * 0.035)))
            open_slots = max(1, 10 - round(ratio * 10))
            if ratio >= 0.82:
                status = "Alta demanda"
                tone = "success"
            elif ratio >= 0.58:
                status = "Ritmo activo"
                tone = str(meta["tone"])
            else:
                status = "Disponible"
                tone = "primary"
            items.append(
                {
                    "field_name": field_name,
                    "location": meta["location"],
                    "address": FIELDS[field_name],
                    "status": status,
                    "occupancy": f"{round(ratio * 100)}% ocupacion",
                    "slots": f"{open_slots} cupos disponibles",
                    "promotion": meta["promotion"],
                    "court_type": meta["court_type"],
                    "peak": meta["peak"],
                    "features": meta["features"],
                    "image_source": meta["image_source"],
                    "occupancy_ratio": ratio,
                    "tone": tone,
                    "is_selected": field_name == selected,
                    "order": index,
                }
            )
        return items

    def _render_live_courts(self) -> None:
        if not self.ids or "live_courts_grid" not in self.ids:
            return
        container = self.ids.live_courts_grid
        container.clear_widgets()
        cards = list(self.live_courts_data or self._build_live_courts_payload([]))
        for item in cards:
            item = dict(item)
            item["is_selected"] = item["field_name"] == self.selected_court_name
            card = ReservationCourtCard()
            card.on_select = self.select_live_court
            card.set_data(item)
            container.add_widget(card)
        selected_meta = FIELD_CARD_META.get(self.selected_court_name, {})
        self.live_court_summary_text = (
            f"{self.selected_court_name} | {selected_meta.get('location', 'Barranquilla')} | "
            f"{selected_meta.get('peak', 'Pico --')}"
        )

    def select_live_court(self, field_name: str) -> None:
        if field_name not in FIELDS:
            return
        self.selected_court_name = field_name
        if self.ids:
            self._suspend_form_events = True
            try:
                self.ids.service_spinner.text = field_name
                self.ids.address_input.text = field_address_for(field_name)
            finally:
                self._suspend_form_events = False
        self._render_live_courts()
        self.update_quote()
        self.selected_range_text = f"Cancha seleccionada: {field_name}"
        self.set_status(f"Cancha seleccionada: {field_name}.")

    def open_date_picker(self) -> None:
        ReservationDatePicker(self.ids.date_input.text if self.ids else "", self.apply_selected_date).open()

    def apply_selected_date(self, selected_date: str) -> None:
        if not self.ids:
            return
        self.ids.date_input.text = selected_date
        self._handle_form_change()
        self.set_status(f"Fecha seleccionada: {selected_date}.")

    def _payload(self) -> dict:
        field_name = self.ids.service_spinner.text.strip()
        return {
            "client_name": self.ids.client_name_input.text,
            "service_type": field_backend_type(field_name),
            "reservation_date": self.ids.date_input.text,
            "start_time": self.ids.start_time_spinner.text,
            "end_time": self.ids.end_time_spinner.text,
            "people_count": self.ids.people_input.text,
            "phone": self.ids.phone_input.text,
            "address": field_address_for(field_name, self.ids.address_input.text),
            "status": self.current_status,
        }

    def _reset_quote_preview(self) -> None:
        self.quote_schedule_text = "Esperando datos para cotizar"
        self.quote_total_text = "$0 COP"
        self.quote_discount_text = "Descuento aplicado: 0%"
        self.quote_promotion_text = "Promociones: Sin promociones"
        self.quote_support_text = "Completa fecha, rango y personas para obtener la cotizacion."
        self.selected_range_text = "Sin rango seleccionado"

    def _set_local_end_options(self, start_time: str) -> None:
        if start_time not in self.start_time_options:
            options = list(END_TIME_OPTIONS)
        else:
            options = [value for value in END_TIME_OPTIONS if value > start_time]

        self.end_time_options = options
        if not self.ids:
            return

        if options:
            if self.ids.end_time_spinner.text not in options:
                self.ids.end_time_spinner.text = options[0]
        else:
            self.ids.end_time_spinner.text = "Sin disponibilidad"

    def _handle_start_time_change(self) -> None:
        if self._suspend_form_events:
            return
        self._set_local_end_options(self.ids.start_time_spinner.text.strip())
        self._handle_form_change()

    def _handle_form_change(self) -> None:
        if self._suspend_form_events or not hasattr(self, "_background_task_versions"):
            return
        self.update_quote()
        self._request_availability_refresh()

    def _selected_field_name(self) -> str:
        if not self.ids:
            return FIELD_NAMES[0]
        return self.ids.service_spinner.text.strip()

    def _can_manage_reservations(self) -> bool:
        role = str((App.get_running_app().current_user or {}).get("role", "")).strip().lower()
        return role == "admin"

    def _format_reservation_promotions(self, pricing) -> str:
        labels = []
        if pricing.weekend_surcharge_percent:
            labels.append(f"Recargo fin de semana +{pricing.weekend_surcharge_percent:.0f}%")
        if pricing.bulk_discount_percent:
            labels.append(f"Promo por grupo -{pricing.bulk_discount_percent:.0f}%")
        return " | ".join(labels) if labels else "Sin promociones activas"

    def _format_promo_label(self, pricing) -> str:
        if pricing.bulk_discount_percent:
            return f"Promo activa: grupo grande (-{pricing.bulk_discount_percent:.0f}%)"
        if pricing.weekend_surcharge_percent:
            return f"Partido prime de fin de semana (+{pricing.weekend_surcharge_percent:.0f}%)"
        return "Partido operativo: tarifa estandar"

    def _match_badge_for(self, status: str, schedule: str, people_count: int) -> str:
        if str(status or "").strip() == "PAID":
            return "Partido pagado"
        if str(status or "").strip() in {"PENDING_PAYMENT", "pending_payment"}:
            return "Checkout activo"
        if int(people_count or 0) >= 8:
            return "Partido destacado"
        if str(schedule or "").strip().lower() == "noche":
            return "Partido prime"
        if str(status or "").strip().lower() in {"confirmada", "confirmed"}:
            return "Partido premium"
        return "Partido en vivo"

    def _payment_tone(self, payment_status: str, reservation_status: str) -> str:
        if payment_status == "paid" or reservation_status in {"PAID", "paid"}:
            return "success"
        if payment_status in {"failed", "cancelled", "refunded"} or reservation_status in {"FAILED", "CANCELLED", "REFUNDED", "EXPIRED", "failed", "cancelled", "refunded", "expired"}:
            return "danger"
        return "warning"

    def _expiration_text(self, expires_at: str | None, reservation_status: str) -> str:
        if reservation_status in {"EXPIRED", "expired"}:
            return "Reserva expirada"
        if reservation_status in {"PAID", "paid"}:
            return "Cupo bloqueado por pago"
        if not expires_at:
            return ""
        try:
            normalized = str(expires_at).replace("Z", "+00:00")
            expiration = datetime.fromisoformat(normalized)
            if expiration.tzinfo is not None:
                minutes = max(0, round((expiration - datetime.now(timezone.utc)).total_seconds() / 60))
            else:
                minutes = max(0, round((expiration - datetime.now()).total_seconds() / 60))
        except ValueError:
            return "Checkout con tiempo limitado"
        return f"Expira en {minutes} min" if minutes else "Expirando ahora"

    def _set_save_feedback(self, message: str, tone: str = "neutral") -> None:
        self.save_feedback_text = message
        self.save_feedback_tone = tone

    def _update_local_smart_suggestion(self) -> None:
        if not self.ids:
            return
        field_name = self._selected_field_name()
        reservation_date = self.ids.date_input.text.strip()
        start_time = self.ids.start_time_spinner.text.strip()
        end_time = self.ids.end_time_spinner.text.strip()
        if not reservation_date or start_time not in self.start_time_options or end_time == "Sin disponibilidad":
            self.smart_suggestion_text = "Sugerencia inteligente: completa fecha y rango."
            return
        try:
            service = self.get_service("reservation_service")
            availability = service.get_daily_availability(field_backend_type(field_name), reservation_date)
            if availability["available_count"] <= 0:
                self.smart_suggestion_text = "Sin cupos libres: prueba otro dia o cancha."
            elif availability["occupied_count"] > availability["available_count"]:
                self.smart_suggestion_text = "Alta demanda: reserva cuanto antes o mueve a horario cercano."
            else:
                self.smart_suggestion_text = (
                    f"Recomendacion: {field_name} mantiene {availability['available_count']} cupos libres; "
                    f"turnaround {10} min protegido."
                )
        except Exception:
            self.smart_suggestion_text = "Sugerencia inteligente no disponible en este momento."

    def _extract_reservation_id(self, reservation) -> int:
        if isinstance(reservation, dict):
            return int(reservation.get("reservation_id") or reservation.get("id") or 0)
        if isinstance(reservation, int):
            return reservation
        return int(getattr(reservation, "id", 0) or 0)

    def on_field_selected(self, field_name: str) -> None:
        if not self.ids:
            return
        if field_name in FIELDS:
            self.selected_court_name = field_name
        self.ids.address_input.text = field_address_for(field_name, "")
        self._render_live_courts()

    def _ensure_valid_field_selection(self) -> bool:
        field_name = self._selected_field_name()
        if field_name not in FIELDS:
            self.notify("Cancha", "Selecciona una de las 5 canchas disponibles.", tone="warning")
            self.set_status("Selecciona una cancha valida para continuar.")
            return False

        expected_address = field_address_for(field_name)
        if self.ids.address_input.text != expected_address:
            self.ids.address_input.text = expected_address
        return True

    def on_edit(self, reservation) -> None:
        reservation_id = self._extract_reservation_id(reservation)
        if not reservation_id:
            self.notify("Reserva", "No se encontro la reserva seleccionada.", tone="warning")
            return
        self.load_reservation(reservation_id)

    def on_confirm(self, reservation) -> None:
        if not self._can_manage_reservations():
            self.notify("Acceso restringido", "Acceso restringido", tone="warning")
            self.set_status("Acceso restringido")
            return
        reservation_id = self._extract_reservation_id(reservation)
        if not reservation_id:
            self.notify("Reserva", "No se encontro la reserva seleccionada.", tone="warning")
            return
        if isinstance(reservation, dict) and str(reservation.get("status", "")).lower() in {"confirmada", "confirmed"}:
            self.notify("Reserva", "La reserva ya estaba confirmada.", tone="primary")
            return
        self.request_confirm_reservation(reservation_id)

    def on_delete(self, reservation) -> None:
        if not self._can_manage_reservations():
            self.notify("Acceso restringido", "Acceso restringido", tone="warning")
            self.set_status("Acceso restringido")
            return
        reservation_id = self._extract_reservation_id(reservation)
        if not reservation_id:
            self.notify("Reserva", "No se encontro la reserva seleccionada.", tone="warning")
            return
        self.request_delete_reservation(reservation_id)

    def on_pay(self, reservation) -> None:
        reservation_id = self._extract_reservation_id(reservation)
        if not reservation_id:
            self.notify("Pago", "No se encontro la reserva seleccionada.", tone="warning")
            return
        self.set_status("Creando checkout de pago...")
        self.run_in_background(
            "reservation_payment",
            lambda: self.get_service("payment_api_service").create_payment(reservation_id),
            self._handle_payment_success,
            self._handle_payment_error,
        )

    def _handle_payment_success(self, payload: dict) -> None:
        payment_url = str(payload.get("payment_url") or "").strip()
        if payment_url:
            webbrowser.open(payment_url)
            self.notify("Checkout listo", "Abrimos el enlace seguro de Mercado Pago.", tone="success")
        else:
            self.notify("Pago pendiente", "La reserva quedo pendiente de pago.", tone="warning")
        App.get_running_app().refresh_screens(["dashboard", "reservations", "calendar", "reports"])

    def _handle_payment_error(self, error: Exception) -> None:
        self.notify("Pago", "No fue posible crear el checkout de pago.", tone="danger")
        self.set_status(f"Error al crear pago: {error}")

    def _request_availability_refresh(self, *, show_loading: bool = True) -> None:
        if not self.ids:
            return

        reservation_date = self.ids.date_input.text.strip()
        field_name = self._selected_field_name()
        service_type = field_backend_type(field_name) if field_name in FIELDS else ""
        start_time = self.ids.start_time_spinner.text.strip()
        end_time = self.ids.end_time_spinner.text.strip()

        if start_time not in self.start_time_options:
            self._set_local_end_options(start_time)
            self.availability_text = "Selecciona fecha, cancha y rango para validar disponibilidad."
            self.availability_color = "neutral"
            self.selected_range_text = "Sin rango seleccionado"
            return

        self._set_local_end_options(start_time)

        if not reservation_date or not service_type:
            self.availability_text = "Selecciona fecha, cancha y rango para validar disponibilidad."
            self.availability_color = "neutral"
            self.selected_range_text = "Sin rango seleccionado"
            return

        if show_loading:
            self.availability_text = "Cargando disponibilidad..."
            self.availability_color = "neutral"
            self.selected_range_text = "Actualizando franjas..."
            self.set_status("Consultando disponibilidad...")

        snapshot = {
            "reservation_date": reservation_date,
            "service_type": service_type,
            "start_time": start_time,
            "end_time": end_time,
            "exclude_reservation_id": self.current_reservation_id or None,
        }
        self.run_in_background(
            "reservations_availability",
            lambda: self._fetch_availability_data(snapshot),
            self._apply_availability_data,
            self._handle_availability_error,
        )

    def _fetch_availability_data(self, snapshot: dict) -> dict:
        reservation_service = self.get_service("reservation_service")
        end_options = reservation_service.get_available_end_times(
            snapshot["service_type"],
            snapshot["reservation_date"],
            snapshot["start_time"],
            exclude_reservation_id=snapshot["exclude_reservation_id"],
        )
        availability = reservation_service.get_daily_availability(
            snapshot["service_type"],
            snapshot["reservation_date"],
            exclude_reservation_id=snapshot["exclude_reservation_id"],
        )

        selected_end = ""
        if end_options:
            selected_end = (
                snapshot["end_time"]
                if snapshot["end_time"] in end_options
                else end_options[0]
            )

        is_available = False
        if selected_end:
            is_available = reservation_service.is_slot_available(
                snapshot["service_type"],
                snapshot["reservation_date"],
                snapshot["start_time"],
                selected_end,
                exclude_reservation_id=snapshot["exclude_reservation_id"],
            )

        return {
            "availability": availability,
            "end_options": end_options,
            "selected_end": selected_end,
            "start_time": snapshot["start_time"],
            "is_available": is_available,
        }

    def _apply_availability_data(self, payload: dict) -> None:
        options = payload["end_options"]
        self.end_time_options = options

        self._suspend_form_events = True
        try:
            if options:
                if self.ids.end_time_spinner.text != payload["selected_end"]:
                    self.ids.end_time_spinner.text = payload["selected_end"]
            else:
                self.ids.end_time_spinner.text = "Sin disponibilidad"
        finally:
            self._suspend_form_events = False

        availability = payload["availability"]
        summary = (
            f"{availability['available_count']} disponibles | "
            f"{availability['occupied_count']} ocupadas | "
            f"{availability['partial_count']} parciales"
        )

        if not availability["has_availability"]:
            self.availability_text = "No hay disponibilidad en este dia."
            self.availability_color = "danger"
            self.selected_range_text = summary
            return

        if payload["selected_end"]:
            if payload["is_available"]:
                self.availability_text = (
                    f"Rango disponible: {payload['start_time']} - {payload['selected_end']}"
                )
                self.availability_color = "success"
            else:
                self.availability_text = "Este horario ya esta reservado."
                self.availability_color = "danger"
            self.selected_range_text = summary
            return

        self.availability_text = "No hay rango valido disponible desde la hora seleccionada."
        self.availability_color = "warning"
        self.selected_range_text = summary

    def _handle_availability_error(self, error: Exception) -> None:
        self.availability_text = "No fue posible cargar la disponibilidad."
        self.availability_color = "danger"
        self.selected_range_text = "Intenta nuevamente."
        self.set_status(f"Error al consultar disponibilidad: {error}")

    def update_quote(self) -> None:
        reservation_date = self.ids.date_input.text.strip()
        start_time = self.ids.start_time_spinner.text.strip()
        end_time = self.ids.end_time_spinner.text.strip()
        people_count = self.ids.people_input.text.strip()

        if not reservation_date or not start_time or not end_time or not people_count or end_time == "Sin disponibilidad":
            self._reset_quote_preview()
            return

        try:
            pricing = self.get_service("reservation_service").get_pricing_preview(
                reservation_date,
                start_time,
                people_count,
                end_time,
            )
        except (ValidationError, ValueError):
            self.quote_schedule_text = "Datos incompletos"
            self.quote_total_text = "$0 COP"
            self.quote_discount_text = "Descuento aplicado: 0%"
            self.quote_promotion_text = "Promociones: Sin promociones"
            self.quote_support_text = "Usa fecha AAAA-MM-DD y una cantidad de personas numerica valida."
            self.selected_range_text = "Sin rango seleccionado"
            return

        promotions = " | ".join(pricing["applied_labels"]) if pricing["applied_labels"] else "Sin promociones"
        smart_rules = pricing.get("smart_rules") or []
        smart_adjustment = float(pricing.get("smart_adjustment", 0.0) or 0.0)
        weekend_text = (
            f"Incluye recargo fin de semana del {pricing['weekend_surcharge_percent']:.0f}%."
            if pricing["weekend_surcharge_percent"]
            else "Sin recargo de fin de semana."
        )
        schedule_label = _display_schedule_label(pricing["schedule"])
        self.quote_schedule_text = f"Jornada {schedule_label} | {pricing['duration_hours']} hora(s)"
        self.quote_total_text = format_currency(pricing["total"])
        self.quote_discount_text = (
            f"Descuento aplicado: {pricing['bulk_discount_percent']:.0f}%"
            if pricing["bulk_discount_percent"]
            else "Descuento aplicado: 0%"
        )
        self.quote_promotion_text = f"Promociones: {promotions}"
        self.quote_support_text = (
            f"Rango: {pricing['time_range']} | Base: {format_currency(pricing['base_price'])} | "
            f"Subtotal: {format_currency(pricing['subtotal'])}. {weekend_text}"
        )
        self.smart_pricing_text = (
            f"Ajuste inteligente: {format_currency(smart_adjustment)} | {'; '.join(smart_rules)}"
            if smart_rules
            else "Tarifa base sin ajuste inteligente activo."
        )
        self.selected_range_text = f"Rango seleccionado: {pricing['time_range']}"
        self._update_local_smart_suggestion()

    def open_calendar(self) -> None:
        app = App.get_running_app()
        shell = app.get_shell_screen()
        if shell is None:
            return
        calendar_screen = shell.ids.inner_sm.get_screen("calendar")
        calendar_screen.open_from_reservation_context(
            self.ids.service_spinner.text,
            self.ids.date_input.text or "",
            self.ids.start_time_spinner.text,
            self.ids.end_time_spinner.text if self.ids.end_time_spinner.text != "Sin disponibilidad" else "",
            self.current_reservation_id,
        )
        shell.switch_screen("calendar")

    def save_reservation(self) -> None:
        if not self._ensure_valid_field_selection():
            self._set_save_feedback("Selecciona una cancha valida para continuar.", "warning")
            return
        payload = self._payload()
        self._set_save_feedback("", "neutral")
        self.set_status("Guardando reserva...")
        if self.ids and "save_button" in self.ids:
            self.ids.save_button.begin_action("Guardando...")
        self.run_in_background(
            "reservation_save",
            lambda: self._perform_save(payload),
            self._handle_save_success,
            self._handle_save_error,
        )

    def _perform_save(self, payload: dict) -> dict:
        reservation_service = self.get_service("reservation_service")
        if self.current_reservation_id:
            reservation_service.update_reservation(self.current_reservation_id, payload)
            return {
                "title": "Reserva actualizada",
                "message": "La reserva fue actualizada correctamente.",
            }

        reservation_service.create_reservation(payload)
        return {
            "title": "Reserva guardada",
            "message": "La reserva fue guardada correctamente.",
        }

    def _handle_save_success(self, payload: dict) -> None:
        if self.ids and "save_button" in self.ids:
            self.ids.save_button.finish_action(flash_tone="success", restore_text=self.save_button_text)
        self.notify(payload["title"], payload["message"], tone="success")
        self.clear_form()
        self._set_save_feedback(payload["message"], "success")
        App.get_running_app().refresh_screens(["dashboard", "reservations", "calendar", "reports"])

    def _handle_save_error(self, error: Exception) -> None:
        if self.ids and "save_button" in self.ids:
            self.ids.save_button.finish_action(flash_tone="danger", restore_text=self.save_button_text)
        if isinstance(error, ReservationConflictValidationError):
            suggestions = "\n".join(
                f"- {item['inicio']} - {item['fin']}"
                for item in error.suggestions
                if item.get("inicio") and item.get("fin")
            )
            message = "Horario ocupado"
            if suggestions:
                message = f"{message}\n\nSugerencias disponibles:\n{suggestions}"
            self._set_save_feedback("Ese horario no esta disponible.", "danger")
            self.notify("Disponibilidad", message, tone="danger")
            return

        if isinstance(error, ValidationError):
            self._set_save_feedback(
                str(error),
                "warning" if "reservado" not in str(error).lower() else "danger",
            )
            self.notify(
                "Validacion",
                str(error),
                tone="warning" if "reservado" not in str(error).lower() else "danger",
            )
            return

        self._set_save_feedback("No fue posible guardar la reserva.", "danger")
        self.notify("Error", "No fue posible guardar la reserva.", tone="danger")
        self.set_status(f"Error al guardar reserva: {error}")

    def clear_form(self) -> None:
        self.current_reservation_id = 0
        self.current_status = "pendiente"
        self.form_heading = "Nuevo partido"
        self.save_button_text = "Guardar partido"
        self._set_save_feedback("", "neutral")
        self._suspend_form_events = True
        try:
            self.ids.client_name_input.text = ""
            default_service = self.service_options[0] if self.service_options else FIELD_NAMES[0]
            self.ids.service_spinner.text = default_service
            self.ids.date_input.text = date.today().isoformat()
            self.ids.start_time_spinner.text = self.start_time_options[0]
            self.end_time_options = [value for value in END_TIME_OPTIONS if value > self.start_time_options[0]]
            self.ids.end_time_spinner.text = self.end_time_options[0]
            self.ids.people_input.text = ""
            self.ids.phone_input.text = ""
            self.ids.address_input.text = field_address_for(default_service)
        finally:
            self._suspend_form_events = False
        self._reset_quote_preview()
        self.availability_text = "Selecciona fecha, cancha y rango para validar disponibilidad."
        self.availability_color = "neutral"
        self.selected_court_name = default_service
        self._render_live_courts()
        self.set_status("Formulario limpio y listo para una nueva reserva.")

    def load_reservation(self, reservation_id: int) -> None:
        self.set_status("Cargando reserva...")
        self.run_in_background(
            "reservation_load",
            lambda: self.get_service("reservation_service").get_reservation(reservation_id),
            self._apply_loaded_reservation,
            self._handle_load_reservation_error,
        )

    def _apply_loaded_reservation(self, reservation) -> None:
        if reservation is None:
            self.notify("Reserva", "No se encontro la reserva seleccionada.", tone="danger")
            self.refresh()
            return

        self.current_reservation_id = reservation.id or 0
        self.current_status = reservation.status
        self.form_heading = f"Editando partido #{reservation.id}"
        self.save_button_text = "Actualizar partido"
        field_name = resolve_field_name(reservation.service_type, reservation.address)
        self._suspend_form_events = True
        try:
            self.ids.client_name_input.text = reservation.client_name
            self.ids.service_spinner.text = field_name
            self.ids.date_input.text = reservation.reservation_date
            self.ids.start_time_spinner.text = reservation.start_time
            self._set_local_end_options(reservation.start_time)
            self.ids.end_time_spinner.text = reservation.end_time
            self.ids.people_input.text = str(reservation.people_count)
            self.ids.phone_input.text = reservation.phone
            self.ids.address_input.text = field_address_for(field_name, reservation.address)
        finally:
            self._suspend_form_events = False
        self.selected_court_name = field_name
        self._render_live_courts()
        self.update_quote()
        self._request_availability_refresh(show_loading=False)
        self.set_status(f"Reserva #{reservation.id} cargada en el formulario.")

    def _handle_load_reservation_error(self, error: Exception) -> None:
        self.notify("Reserva", "No fue posible cargar la reserva seleccionada.", tone="danger")
        self.set_status(f"Error al cargar reserva: {error}")

    def apply_calendar_selection(self, payload: dict) -> None:
        default_service = self.service_options[0] if self.service_options else FIELD_NAMES[0]
        field_name = resolve_field_name(payload.get("service_type", ""), payload.get("address", ""))
        self._suspend_form_events = True
        try:
            self.ids.service_spinner.text = field_name or default_service
            self.ids.date_input.text = payload.get("reservation_date", "")
            self.ids.start_time_spinner.text = payload.get("start_time", self.start_time_options[0])
            self._set_local_end_options(self.ids.start_time_spinner.text)
            if payload.get("end_time") in self.end_time_options:
                self.ids.end_time_spinner.text = payload["end_time"]
            self.ids.address_input.text = field_address_for(self.ids.service_spinner.text, field_address_for(default_service))
        finally:
            self._suspend_form_events = False
        self.selected_court_name = self.ids.service_spinner.text
        self._render_live_courts()
        self.update_quote()
        self._request_availability_refresh(show_loading=False)
        self.set_status("Rango recibido desde el calendario de disponibilidad.")

    def confirm_reservation(self, reservation_id: int) -> None:
        if not self._can_manage_reservations():
            self.notify("Acceso restringido", "Acceso restringido", tone="warning")
            self.set_status("Acceso restringido")
            return
        self.set_status("Confirmando reserva...")
        self.run_in_background(
            "reservation_confirm",
            lambda: self._perform_confirm(reservation_id),
            lambda _payload: self._handle_confirm_success(reservation_id),
            self._handle_confirm_error,
        )

    def _perform_confirm(self, reservation_id: int) -> dict:
        self.get_service("reservation_service").confirm_reservation(reservation_id)
        return {"reservation_id": reservation_id}

    def _handle_confirm_success(self, reservation_id: int) -> None:
        if self.current_reservation_id == reservation_id:
            self.current_status = "confirmed"
        self.notify("Reserva confirmada", "La reserva fue marcada como confirmada.", tone="success")
        App.get_running_app().refresh_screens(["dashboard", "reservations", "calendar", "reports"])

    def _handle_confirm_error(self, error: Exception) -> None:
        self.notify("Reserva", "No fue posible confirmar la reserva.", tone="danger")
        self.set_status(f"Error al confirmar reserva: {error}")

    def request_delete_reservation(self, reservation_id: int) -> None:
        if not self._can_manage_reservations():
            self.notify("Acceso restringido", "Acceso restringido", tone="warning")
            self.set_status("Acceso restringido")
            return
        self.confirm_action(
            "Eliminar reserva",
            "\u00bfEst\u00e1s seguro?",
            lambda: self._delete_reservation(reservation_id),
            tone="danger",
            confirm_text="Si, eliminar",
        )

    def _delete_reservation(self, reservation_id: int) -> None:
        if not self._can_manage_reservations():
            self.notify("Acceso restringido", "Acceso restringido", tone="warning")
            self.set_status("Acceso restringido")
            return
        self.set_status("Eliminando reserva...")
        self.run_in_background(
            "reservation_delete",
            lambda: self._perform_delete(reservation_id),
            lambda _payload: self._handle_delete_success(reservation_id),
            self._handle_delete_error,
        )

    def request_confirm_reservation(self, reservation_id: int) -> None:
        if not self._can_manage_reservations():
            self.notify("Acceso restringido", "Acceso restringido", tone="warning")
            self.set_status("Acceso restringido")
            return
        self.confirm_action(
            "Confirmar reserva",
            "\u00bfEst\u00e1s seguro?",
            lambda: self.confirm_reservation(reservation_id),
            tone="success",
            confirm_text="Si, confirmar",
        )

    def _perform_delete(self, reservation_id: int) -> dict:
        self.get_service("reservation_service").delete_reservation(reservation_id)
        return {"reservation_id": reservation_id}

    def _handle_delete_success(self, reservation_id: int) -> None:
        if self.current_reservation_id == reservation_id:
            self.clear_form()
        self.notify("Reserva eliminada", "La reserva fue eliminada correctamente.", tone="danger")
        App.get_running_app().refresh_screens(["dashboard", "reservations", "calendar", "reports"])

    def _handle_delete_error(self, error: Exception) -> None:
        self.notify("Reserva", "No fue posible eliminar la reserva.", tone="danger")
        self.set_status(f"Error al eliminar reserva: {error}")
