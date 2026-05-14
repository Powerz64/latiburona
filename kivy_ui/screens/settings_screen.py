from __future__ import annotations

from kivy.app import App
from kivy.metrics import dp
from kivy.properties import BooleanProperty, StringProperty

from app.utils.constants import DEFAULT_SETTINGS
from app.utils.formatters import format_currency
from app.utils.validators import ValidationError
from kivy_ui.screens.base_screen import ServiceScreen


class SettingsScreen(ServiceScreen):
    preview_text = StringProperty("")
    location_text = StringProperty("")
    rules_text = StringProperty("")
    theme_note_text = StringProperty("La preferencia visual se guarda localmente en este equipo.")
    active_theme_text = StringProperty("Tema activo: Oscuro")
    account_name_text = StringProperty("Sin sesión activa")
    account_email_text = StringProperty("")
    account_role_text = StringProperty("")
    header_role_badge_text = StringProperty("ADMIN")
    header_access_text = StringProperty("Control completo")
    header_theme_text = StringProperty("Modo oscuro")
    header_sync_text = StringProperty("Sincronizado")
    dark_button_variant = StringProperty("primary")
    light_button_variant = StringProperty("secondary")
    show_pricing_controls = BooleanProperty(True)

    def on_kv_post(self, *_args) -> None:
        self.bind(size=self._update_layout)
        self._update_layout()

    def _update_layout(self, *_args) -> None:
        if not self.ids:
            return
        self.ids.content_grid.orientation = "vertical" if self.width < dp(1200) or not self.show_pricing_controls else "horizontal"

    def refresh(self) -> None:
        self.set_status("Cargando configuración...")
        print(f"LOAD START: {self.name}", flush=True)
        self.run_in_background(
            "settings_refresh",
            self._fetch_settings_data,
            self._apply_settings_payload,
            self._handle_settings_payload_error,
        )

    def _fetch_settings_data(self) -> dict:
        settings = self.get_service("settings_service").load_settings()
        user = dict(App.get_running_app().current_user or {})
        return {
            "settings": settings,
            "user": user,
        }

    def _apply_settings_data(self, payload: dict) -> None:
        settings = payload["settings"]
        self.ids.morning_input.text = f"{settings.price_morning:.0f}"
        self.ids.afternoon_input.text = f"{settings.price_afternoon:.0f}"
        self.ids.night_input.text = f"{settings.price_night:.0f}"
        self.ids.weekend_input.text = f"{settings.weekend_surcharge:.0f}"
        self.ids.bulk_threshold_input.text = str(settings.bulk_people_threshold)
        self.ids.bulk_discount_input.text = f"{settings.bulk_discount:.0f}"
        self.ids.children_switch.active = settings.allow_children
        self.ids.pets_switch.active = settings.allow_pets

        self.preview_text = self._build_preview(
            settings.price_morning,
            settings.price_afternoon,
            settings.price_night,
            settings.weekend_surcharge,
            settings.bulk_people_threshold,
            settings.bulk_discount,
        )
        self.location_text = (
            "Cobertura local: Riomar, Villa Campestre, Norte Centro Historico, "
            "La Castellana y Suroriente. Cada sede muestra accesos, referencias y "
            "promociones útiles para operar con contexto de Barranquilla."
        )
        self.rules_text = (
            f"Se aceptan niños: {'Sí' if settings.allow_children else 'No'}\n"
            f"Se aceptan mascotas: {'Sí' if settings.allow_pets else 'No'}\n"
            f"Recargo fin de semana: {settings.weekend_surcharge:.0f}%\n"
            f"Descuento grupal: {settings.bulk_discount:.0f}% desde {settings.bulk_people_threshold} personas"
        )

        user = payload["user"]
        role = str(user.get("role") or "").strip().lower()
        self.show_pricing_controls = role == "admin" or bool(user.get("is_admin"))
        if not self.show_pricing_controls:
            self.rules_text = (
                f"Se aceptan niños: {'Sí' if settings.allow_children else 'No'}\n"
                f"Se aceptan mascotas: {'Si' if settings.allow_pets else 'No'}"
            )
        self.account_name_text = user.get("display_name") or user.get("full_name") or "Sin sesión activa"
        self.account_email_text = user.get("email", "")
        self.account_role_text = "Administrador" if self.show_pricing_controls else "Operador"
        self.header_role_badge_text = "ADMIN" if self.show_pricing_controls else "OPERADOR"
        self.header_access_text = "Control completo" if self.show_pricing_controls else "Vista operativa"
        self.header_sync_text = "Sincronizado"
        self._apply_theme_state(App.get_running_app().theme_mode)
        self.set_status("Configuración del negocio y experiencia visual cargadas.")

    def _handle_settings_error(self, error: Exception) -> None:
        self.set_status(f"Error al cargar configuración: {error}")

    def _apply_settings_payload(self, payload: dict) -> None:
        try:
            self._apply_settings_data(payload)
        finally:
            print(f"LOAD END: {self.name}", flush=True)

    def _handle_settings_payload_error(self, error: Exception) -> None:
        try:
            self._handle_settings_error(error)
        finally:
            print(f"LOAD END: {self.name}", flush=True)

    def _apply_theme_state(self, mode: str) -> None:
        self.active_theme_text = "Tema activo: Oscuro" if mode == "dark" else "Tema activo: Claro"
        self.header_theme_text = "Modo oscuro" if mode == "dark" else "Modo claro"
        self.dark_button_variant = "primary" if mode == "dark" else "secondary"
        self.light_button_variant = "primary" if mode == "light" else "secondary"

    def on_theme_applied(self, mode: str) -> None:
        self._apply_theme_state(mode)

    def _build_preview(
        self,
        morning: float,
        afternoon: float,
        night: float,
        weekend_surcharge: float,
        bulk_threshold: int,
        bulk_discount: float,
    ) -> str:
        tarifas = (
            f"Mañana: {format_currency(morning)} | "
            f"Tarde: {format_currency(afternoon)} | "
            f"Noche Prime: {format_currency(night)}"
        )
        return (
            "La Jaula Barranquilla\n"
            "Ubicación: Vía 40 #85-470, Riomar.\n"
            "Cómo llegar: acceso rápido desde Circunvalar y Vía 40; entrada principal junto al corredor universitario.\n"
            "Referencias: cerca de Viva Barranquilla y a pocos minutos del Romelio Martínez.\n"
            "Parqueadero: privado disponible con ingreso controlado.\n"
            "Horas más activas: 7PM-10PM | Recomendado: 6AM-9AM para madrugadores.\n"
            f"Tarifas: {tarifas}.\n"
            f"Promociones: 20% de descuento para madrugadores; descuento grupos {bulk_threshold}+ (-{bulk_discount:.0f}%); balón gratis en horario nocturno.\n"
            "Característica: cancha premium de alta rotación para partidos competitivos.\n\n"
            "Brazuca Soccer\n"
            "Ubicación: Calle 3 #23-90, Villa Campestre.\n"
            "Cómo llegar: ruta directa desde corredor universitario y acceso norte.\n"
            "Referencias: cerca de universidades, conjuntos residenciales y vía a Puerto Colombia.\n"
            "Parqueadero: bahías laterales y zona de descenso rápido.\n"
            "Horas más activas: 5PM-8PM | Recomendado: 4PM-6PM para ligas universitarias.\n"
            f"Tarifas: {tarifas}.\n"
            "Promociones: Liga universitaria con bebidas gratis para 5+ jugadores; bloque posjornada con prioridad.\n"
            "Característica: sintética 7v7 con ambiente joven y alto flujo entre semana.\n\n"
            "Brasileirao\n"
            "Ubicación: Carrera 46 #76-109, Norte Centro Histórico.\n"
            "Cómo llegar: entrada principal sobre Carrera 46 con conexión rápida hacia Prado y Alto Prado.\n"
            "Referencias: a 8 minutos del Romelio Martínez y cerca de corredores de rumba nocturna.\n"
            "Parqueadero: cupos frontales y vigilancia de acceso.\n"
            "Horas más activas: 8PM-11PM | Recomendado: después de 8PM para Noche Prime.\n"
            f"Tarifas: {tarifas}; recargo fin de semana {weekend_surcharge:.0f}%.\n"
            "Promociones: balón incluido después de 8PM y prioridad para partidos prime.\n"
            "Característica: grama tech y luces fuertes para partidos nocturnos.\n\n"
            "La Castellana\n"
            "Ubicación: Carrera 53 #94-160, La Castellana.\n"
            "Cómo llegar: acceso por Carrera 53 con rutas rápidas desde Buenavista y Viva.\n"
            "Referencias: zona familiar, restaurantes cercanos y parqueaderos de apoyo.\n"
            "Parqueadero: fácil acceso para familias y visitantes.\n"
            "Horas más activas: sábados 4PM-8PM | Recomendado: domingos familiares.\n"
            f"Tarifas: {tarifas}.\n"
            "Promociones: Fin de semana familiar; niños entran gratis los domingos.\n"
            "Característica: cancha cómoda para planes familiares y partidos recreativos.\n\n"
            "Soccer House\n"
            "Ubicación: Calle 25 #3-126, Suroriente.\n"
            "Cómo llegar: ruta rápida desde Murillo con descenso junto a la entrada.\n"
            "Referencias: cerca de barrios residenciales y comercio local.\n"
            "Parqueadero: zona de motos y carros con acceso rapido.\n"
            "Horas más activas: 6PM-9PM | Recomendado: martes de reto y bloques comunitarios.\n"
            f"Tarifas: {tarifas}.\n"
            "Promociones: Reto de martes; 2 horas por precio de 1.5.\n"
            "Característica: cancha comunitaria con alta recurrencia de equipos locales."
        )

    def save_settings(self) -> None:
        payload = {
            "price_morning": self.ids.morning_input.text,
            "price_afternoon": self.ids.afternoon_input.text,
            "price_night": self.ids.night_input.text,
            "weekend_surcharge": self.ids.weekend_input.text,
            "bulk_people_threshold": self.ids.bulk_threshold_input.text,
            "bulk_discount": self.ids.bulk_discount_input.text,
            "allow_children": self.ids.children_switch.active,
            "allow_pets": self.ids.pets_switch.active,
        }
        self.set_status("Guardando configuración...")
        self.run_in_background(
            "settings_save",
            lambda: self.get_service("settings_service").save_settings(payload),
            self._handle_save_success,
            self._handle_save_error,
        )

    def _handle_save_success(self, settings) -> None:
        self.preview_text = self._build_preview(
            settings.price_morning,
            settings.price_afternoon,
            settings.price_night,
            settings.weekend_surcharge,
            settings.bulk_people_threshold,
            settings.bulk_discount,
        )
        self.rules_text = (
            f"Se aceptan niños: {'Sí' if settings.allow_children else 'No'}\n"
            f"Se aceptan mascotas: {'Sí' if settings.allow_pets else 'No'}\n"
            f"Recargo fin de semana: {settings.weekend_surcharge:.0f}%\n"
            f"Descuento grupal: {settings.bulk_discount:.0f}% desde {settings.bulk_people_threshold} personas"
        )
        self.notify("Configuración guardada", "Los cambios se guardaron correctamente.", tone="success")
        self.set_status("Configuración guardada correctamente.")
        App.get_running_app().refresh_screens(["dashboard", "reservations", "reports", "settings"])

    def _handle_save_error(self, error: Exception) -> None:
        if isinstance(error, ValidationError):
            self.notify("Validacion", str(error), tone="warning")
            return
        self.notify("Configuración", "No fue posible guardar la configuración.", tone="danger")
        self.set_status(f"Error al guardar configuración: {error}")

    def restore_defaults(self) -> None:
        self.ids.morning_input.text = str(int(DEFAULT_SETTINGS["price_morning"]))
        self.ids.afternoon_input.text = str(int(DEFAULT_SETTINGS["price_afternoon"]))
        self.ids.night_input.text = str(int(DEFAULT_SETTINGS["price_night"]))
        self.ids.weekend_input.text = str(int(DEFAULT_SETTINGS["weekend_surcharge"]))
        self.ids.bulk_threshold_input.text = str(DEFAULT_SETTINGS["bulk_people_threshold"])
        self.ids.bulk_discount_input.text = str(int(DEFAULT_SETTINGS["bulk_discount"]))
        self.ids.children_switch.active = bool(DEFAULT_SETTINGS["allow_children"])
        self.ids.pets_switch.active = bool(DEFAULT_SETTINGS["allow_pets"])
        self.preview_text = "Valores por defecto cargados. Presiona Guardar cambios para aplicarlos."
        self.rules_text = "Reglas restauradas localmente. Guarda para aplicarlas en el sistema."
        self.set_status("Valores por defecto listos para aplicarse.")

    def activate_dark_theme(self) -> None:
        App.get_running_app().apply_theme_mode("dark")

    def activate_light_theme(self) -> None:
        App.get_running_app().apply_theme_mode("light")

    def logout(self) -> None:
        App.get_running_app().logout()
