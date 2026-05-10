from __future__ import annotations

import unicodedata

from kivy.app import App
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty

from app.services import ReservationConflictValidationError
from app.utils.constants import END_TIME_OPTIONS, SERVICE_TYPES, TIME_OPTIONS
from app.utils.formatters import format_currency, format_date, format_reservation_window
from app.utils.validators import ValidationError
from kivy_ui.components.rows import ReservationRow
from kivy_ui.screens.base_screen import ServiceScreen


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

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._suspend_form_events = False

    def on_kv_post(self, *_args) -> None:
        self.bind(size=self._update_layout)
        self.ids.date_input.bind(text=lambda *_args: self._handle_form_change())
        self.ids.service_spinner.bind(text=lambda *_args: self._handle_form_change())
        self.ids.start_time_spinner.bind(text=lambda *_args: self._handle_start_time_change())
        self.ids.end_time_spinner.bind(text=lambda *_args: self._handle_form_change())
        self.ids.people_input.bind(text=lambda *_args: self.update_quote())
        self._set_service_options(list(FIELD_NAMES))
        self.on_field_selected(self.ids.service_spinner.text)
        self._update_layout()
        self._reset_quote_preview()

    def _update_layout(self, *_args) -> None:
        if not self.ids:
            return
        self.ids.content_grid.cols = 1 if self.width < dp(1180) else 2
        self.ids.form_grid.cols = 1 if self.width < dp(1160) else 2

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
        confirmed_count = len([item for item in reservations if item.status == "confirmada"])

        reservations_payload = []
        for reservation in reservations:
            field_name = resolve_field_name(reservation.service_type, reservation.address)
            pricing = pricing_service.calculate_price(
                reservation.reservation_date,
                reservation.start_time,
                reservation.people_count,
                reservation.end_time,
            )
            promotions = " | ".join(pricing.applied_labels) if pricing.applied_labels else "Sin promociones"
            discount_text = (
                f"Descuento aplicado: {pricing.bulk_discount_percent:.0f}%"
                if pricing.bulk_discount_percent
                else "Sin descuento aplicado"
            )
            reservations_payload.append(
                {
                    "reservation_id": reservation.id or 0,
                    "data": {
                        "reservation_id": reservation.id or 0,
                        "field_name": field_name,
                        "service_type": reservation.service_type,
                        "address": reservation.address,
                        "status": reservation.status,
                    },
                    "client_name": reservation.client_name,
                    "service_type": field_name,
                    "datetime_text": (
                        f"{format_date(reservation.reservation_date)} | "
                        f"{format_reservation_window(reservation.start_time, reservation.end_time)}"
                    ),
                    "people_text": f"{reservation.people_count} personas",
                    "schedule_text": _display_schedule_label(reservation.schedule),
                    "status_text": reservation.status.title(),
                    "status_tone": "success" if reservation.status == "confirmada" else "warning",
                    "promotion_text": promotions,
                    "discount_text": discount_text,
                    "total_text": format_currency(reservation.total),
                    "is_confirmed": reservation.status == "confirmada",
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
            self.empty_state_text = payload["empty_state_text"]
        finally:
            self._suspend_form_events = False
        self._render_reservations()
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
        if self._suspend_form_events:
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

    def _set_save_feedback(self, message: str, tone: str = "neutral") -> None:
        self.save_feedback_text = message
        self.save_feedback_tone = tone

    def _extract_reservation_id(self, reservation) -> int:
        if isinstance(reservation, dict):
            return int(reservation.get("reservation_id") or reservation.get("id") or 0)
        if isinstance(reservation, int):
            return reservation
        return int(getattr(reservation, "id", 0) or 0)

    def on_field_selected(self, field_name: str) -> None:
        if not self.ids:
            return
        self.ids.address_input.text = field_address_for(field_name, "")

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
        if isinstance(reservation, dict) and str(reservation.get("status", "")).lower() == "confirmada":
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
        self.selected_range_text = f"Rango seleccionado: {pricing['time_range']}"

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
            self.ids.date_input.text = ""
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
            self.current_status = "confirmada"
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
