from __future__ import annotations

from datetime import date, datetime, timedelta

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty

from app.utils.constants import END_TIME_OPTIONS, TIME_OPTIONS
from app.utils.time_slots import hour_slots_between, next_time_value
from kivy_ui.components import DayChipButton, SlotButton
from kivy_ui.screens.reservations_screen import FIELD_NAMES, FIELDS, field_backend_type, resolve_field_name
from kivy_ui.screens.base_screen import ServiceScreen


SLOT_LABELS = {
    "available": "Libre",
    "partial": "Parcial",
    "occupied": "Ocupada",
}


class CalendarScreen(ServiceScreen):
    service_options = ListProperty(FIELD_NAMES)
    start_time_options = ListProperty(TIME_OPTIONS)
    end_time_options = ListProperty(END_TIME_OPTIONS)
    selected_service = StringProperty(FIELD_NAMES[0])
    selected_date = StringProperty("")
    selected_start_time = StringProperty("")
    selected_end_time = StringProperty("")
    week_label = StringProperty("")
    availability_text = StringProperty("Selecciona una cancha y una fecha para revisar disponibilidad.")
    selected_range_text = StringProperty("Sin rango seleccionado")
    occupied_ranges_text = StringProperty("Sin reservas registradas para este día.")
    legend_text = StringProperty("Verde: libre | Amarillo: parcial | Rojo: ocupado")
    empty_state_text = StringProperty("")
    has_availability = BooleanProperty(True)
    exclude_reservation_id = NumericProperty(0)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._week_anchor = date.today()
        self._suspend_control_events = False

    def on_kv_post(self, *_args) -> None:
        self.bind(size=self._update_layout)
        self.service_options = list(FIELD_NAMES)
        self._update_layout()

    def _update_layout(self, *_args) -> None:
        if not self.ids:
            return
        self.ids.calendar_body.cols = 1 if self.width < dp(1300) else 2

    def refresh(self) -> None:
        self._suspend_control_events = True
        try:
            if not self.selected_date:
                self.selected_date = date.today().isoformat()
            if not self.selected_start_time:
                self.selected_start_time = self.start_time_options[0]
            if not self.selected_end_time:
                self.selected_end_time = next_time_value(self.selected_start_time)
        finally:
            Clock.schedule_once(lambda _dt: self._release_control_events(), 0)

        self._week_anchor = datetime.strptime(self.selected_date, "%Y-%m-%d").date()
        self._request_calendar_refresh("Cargando calendario...", use_cached_preview=True)

    def _release_control_events(self) -> None:
        self._suspend_control_events = False

    def _set_service_options(self, options: list[str]) -> None:
        resolved_options = list(FIELD_NAMES)
        self.service_options = resolved_options
        if self.selected_service not in resolved_options:
            self.selected_service = resolved_options[0]
        if self.ids and self.ids.service_spinner.text != self.selected_service:
            self._suspend_control_events = True
            try:
                self.ids.service_spinner.text = self.selected_service
            finally:
                self._suspend_control_events = False

    def _request_calendar_refresh(
        self,
        loading_message: str = "Cargando disponibilidad...",
        *,
        use_cached_preview: bool = False,
    ) -> None:
        self.set_status(loading_message)

        snapshot = {
            "selected_service": self.selected_service or (self.service_options[0] if self.service_options else FIELD_NAMES[0]),
            "selected_date": self.selected_date or date.today().isoformat(),
            "selected_start_time": self.selected_start_time or self.start_time_options[0],
            "selected_end_time": self.selected_end_time,
            "exclude_reservation_id": self.exclude_reservation_id or None,
        }
        self.load_data(
            "calendar_refresh",
            lambda: self._fetch_calendar_data(snapshot),
            self._apply_calendar_data,
            self._handle_calendar_error,
            cache_name="calendar",
            loading_message=loading_message,
            use_cached_preview=use_cached_preview,
        )

    def _fetch_calendar_data(self, snapshot: dict) -> dict:
        remote_mode = self.get_service("sync_mode") == "remote"
        api_client = self.get_service("api_client")

        reservation_service = self.get_service("reservation_service")

        service_options = list(FIELD_NAMES)
        selected_service = (
            snapshot["selected_service"]
            if snapshot["selected_service"] in service_options
            else service_options[0]
        )
        backend_service_type = field_backend_type(selected_service)
        week_days = reservation_service.get_week_availability(backend_service_type, snapshot["selected_date"])
        end_options = reservation_service.get_available_end_times(
            backend_service_type,
            snapshot["selected_date"],
            snapshot["selected_start_time"],
            exclude_reservation_id=snapshot["exclude_reservation_id"],
        )
        availability = reservation_service.get_daily_availability(
            backend_service_type,
            snapshot["selected_date"],
            exclude_reservation_id=snapshot["exclude_reservation_id"],
        )

        selected_end = ""
        if end_options:
            selected_end = (
                snapshot["selected_end_time"]
                if snapshot["selected_end_time"] in end_options
                else end_options[0]
            )

        is_available = False
        if selected_end:
            is_available = reservation_service.is_slot_available(
                backend_service_type,
                snapshot["selected_date"],
                snapshot["selected_start_time"],
                selected_end,
                exclude_reservation_id=snapshot["exclude_reservation_id"],
            )

        payload = {
            "service_options": service_options,
            "selected_service": selected_service,
            "week_days": week_days,
            "week_label": self._week_title(week_days),
            "end_options": end_options,
            "selected_end": selected_end,
            "availability": availability,
            "selected_start_time": snapshot["selected_start_time"],
            "selected_date": snapshot["selected_date"],
            "is_available": is_available,
            "offline_mode": False,
        }

        if remote_mode and api_client.last_error == "network_error":
            raise RuntimeError("network_error")
        return payload

    def _apply_calendar_data(self, payload: dict) -> None:
        self._suspend_control_events = True
        try:
            self.selected_service = payload["selected_service"]
            self.selected_date = payload["selected_date"]
            self.selected_start_time = payload["selected_start_time"]
            self._set_service_options(payload["service_options"])
            self.week_label = (
                f"{payload['week_label']} | Modo offline"
                if payload.get("offline_mode")
                else payload["week_label"]
            )
            self._render_week_days(payload["week_days"])

            self.end_time_options = payload["end_options"]
            self.selected_end_time = payload["selected_end"]
            if self.ids:
                target_end_text = self.selected_end_time or "Sin disponibilidad"
                if self.ids.service_spinner.text != self.selected_service:
                    self.ids.service_spinner.text = self.selected_service
                if self.ids.start_time_spinner.text != self.selected_start_time:
                    self.ids.start_time_spinner.text = self.selected_start_time
                if self.ids.end_time_spinner.text != target_end_text:
                    self.ids.end_time_spinner.text = target_end_text
        finally:
            self._suspend_control_events = False

        availability = payload["availability"]
        self.has_availability = availability["has_availability"]
        self.empty_state_text = "" if availability["has_availability"] else "No hay disponibilidad en este dia"
        summary = (
            f"{availability['available_count']} franjas disponibles | "
            f"{availability['occupied_count']} ocupadas | "
            f"{availability['partial_count']} parciales"
        )
        if payload["selected_end"] and payload["is_available"]:
            availability_text = (
                f"{summary} | Rango disponible: {payload['selected_start_time']} - {payload['selected_end']}"
            )
        elif payload["selected_end"]:
            availability_text = (
                f"{summary} | Este rango presenta conflicto de disponibilidad."
            )
        else:
            availability_text = summary

        self.availability_text = (
            f"Modo offline | {availability_text}"
            if payload.get("offline_mode")
            else availability_text
        )
        self.selected_range_text = (
            f"Rango seleccionado: {payload['selected_start_time']} - {payload['selected_end']}"
            if payload["selected_end"]
            else "Sin rango seleccionado"
        )
        self.occupied_ranges_text = (
            "\n".join(
                f"- {item['time_range']} | {item['client_name']} | {item['status']}"
                for item in availability["occupied_ranges"]
            )
            if availability["occupied_ranges"]
            else "Sin reservas registradas para este día."
        )
        self._render_slots(availability["slots"])
        self.set_status(
            "Modo offline: mostrando la ultima disponibilidad guardada."
            if payload.get("offline_mode")
            else "Calendario de disponibilidad actualizado."
        )

    def _handle_calendar_error(self, error: Exception) -> None:
        self.availability_text = "No fue posible cargar la disponibilidad."
        self.selected_range_text = "Intenta nuevamente."
        self.occupied_ranges_text = "No fue posible cargar las reservas ocupadas."
        self.empty_state_text = ""
        self.set_status(f"Error al cargar calendario: {error}")

    def go_previous_week(self) -> None:
        self._week_anchor = self._week_anchor - timedelta(days=7)
        self.selected_date = self._week_anchor.isoformat()
        self._request_calendar_refresh("Cargando semana anterior...")

    def go_next_week(self) -> None:
        self._week_anchor = self._week_anchor + timedelta(days=7)
        self.selected_date = self._week_anchor.isoformat()
        self._request_calendar_refresh("Cargando semana siguiente...")

    def select_day(self, value: str) -> None:
        self.selected_date = value
        self._week_anchor = datetime.strptime(value, "%Y-%m-%d").date()
        self._request_calendar_refresh()

    def on_service_selected(self, value: str) -> None:
        if self._suspend_control_events:
            return
        self.selected_service = value
        self._request_calendar_refresh()

    def on_start_time_selected(self, value: str) -> None:
        if self._suspend_control_events:
            return
        self.selected_start_time = value
        self._request_calendar_refresh("Cargando disponibilidad por hora...")

    def on_end_time_selected(self, value: str) -> None:
        if self._suspend_control_events:
            return
        self.selected_end_time = "" if value == "Sin disponibilidad" else value
        self._request_calendar_refresh("Cargando disponibilidad...")

    def pick_slot(self, slot_time: str) -> None:
        self.selected_start_time = slot_time
        if self.ids and self.ids.start_time_spinner.text != slot_time:
            self.ids.start_time_spinner.text = slot_time
        self._request_calendar_refresh("Cargando rango seleccionado...")

    def open_from_reservation_context(
        self,
        service_type: str,
        reservation_date: str,
        start_time: str,
        end_time: str,
        reservation_id: int = 0,
    ) -> None:
        default_service = self.service_options[0] if self.service_options else FIELD_NAMES[0]
        self.selected_service = resolve_field_name(service_type, "")
        self.selected_date = reservation_date or date.today().isoformat()
        self.selected_start_time = start_time or self.start_time_options[0]
        self.selected_end_time = end_time or next_time_value(self.selected_start_time)
        self.exclude_reservation_id = reservation_id
        if self.ids:
            self._suspend_control_events = True
            try:
                self.ids.service_spinner.text = self.selected_service
                self.ids.start_time_spinner.text = self.selected_start_time
            finally:
                self._suspend_control_events = False
        self.refresh()

    def apply_selection_to_reservation(self) -> None:
        if not self.selected_start_time or not self.selected_end_time:
            self.notify("Rango incompleto", "Selecciona una hora de inicio y una hora de fin.", tone="warning")
            return

        self.set_status("Validando rango seleccionado...")
        self.run_in_background(
            "calendar_apply_selection",
            self._validate_selected_range,
            self._apply_validated_selection,
            self._handle_apply_selection_error,
        )

    def _validate_selected_range(self) -> dict:
        reservation_service = self.get_service("reservation_service")
        is_available = reservation_service.is_slot_available(
            field_backend_type(self.selected_service),
            self.selected_date,
            self.selected_start_time,
            self.selected_end_time,
            exclude_reservation_id=self.exclude_reservation_id or None,
        )
        return {"is_available": is_available}

    def _apply_validated_selection(self, payload: dict) -> None:
        if not payload["is_available"]:
            self.notify("Disponibilidad", "Este horario ya esta reservado.", tone="danger")
            return

        app = App.get_running_app()
        shell = app.get_shell_screen()
        if shell is None:
            return
        reservations_screen = shell.ids.inner_sm.get_screen("reservations")
        reservations_screen.apply_calendar_selection(
            {
                "service_type": self.selected_service,
                "reservation_date": self.selected_date,
                "start_time": self.selected_start_time,
                "end_time": self.selected_end_time,
            }
        )
        shell.switch_screen("reservations")
        self.notify("Rango aplicado", "El rango fue enviado al formulario de reservas.", tone="success")

    def _handle_apply_selection_error(self, error: Exception) -> None:
        self.notify("Disponibilidad", "No fue posible validar el rango seleccionado.", tone="danger")
        self.set_status(f"Error al validar rango: {error}")

    def _render_week_days(self, days: list[dict]) -> None:
        container = self.ids.days_grid
        container.clear_widgets()

        for item in days:
            button = DayChipButton(
                text=f"{item['weekday']}\n{item['day_number']}",
                is_active=item["date"] == self.selected_date,
            )
            button.bind(on_release=lambda _instance, date_value=item["date"]: self.select_day(date_value))
            container.add_widget(button)

    def _render_slots(self, slots: list[dict]) -> None:
        container = self.ids.slots_grid
        container.clear_widgets()

        for item in slots:
            is_selected = item["time"] in self._selected_slots()
            status_label = SLOT_LABELS.get(item["status"], "Libre")
            button = SlotButton(
                text=f"{item['time']}\n{status_label}",
                slot_time=item["time"],
                slot_status=item["status"],
                disabled=item["disabled"],
                is_selected=is_selected,
            )
            button.bind(on_release=lambda _instance, slot_time=item["time"]: self.pick_slot(slot_time))
            container.add_widget(button)

    def _selected_slots(self) -> list[str]:
        if not self.selected_start_time or not self.selected_end_time:
            return []
        return hour_slots_between(self.selected_start_time, self.selected_end_time)

    def _week_title(self, days: list[dict]) -> str:
        if not days:
            return "Semana sin datos"
        start_label = datetime.strptime(days[0]["date"], "%Y-%m-%d").strftime("%d/%m")
        end_label = datetime.strptime(days[-1]["date"], "%Y-%m-%d").strftime("%d/%m")
        return f"Semana {start_label} - {end_label}"
