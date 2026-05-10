from __future__ import annotations

from kivy.app import App
from kivy.clock import Clock
from kivy.properties import BooleanProperty, StringProperty
from kivy.uix.screenmanager import NoTransition

from app.services import AuthApiNetworkError, AuthApiServiceError
from kivy_ui.screens.base_screen import ServiceScreen


class RegisterScreen(ServiceScreen):
    feedback_text = StringProperty("")
    feedback_tone = StringProperty("neutral")
    submitting = BooleanProperty(False)

    def refresh(self) -> None:
        self.set_status("Crea una cuenta para acceder a LaTiburona.")

    def set_feedback(self, message: str, tone: str = "neutral") -> None:
        self.feedback_text = message
        self.feedback_tone = tone

    def open_login(self) -> None:
        self.set_feedback("", "neutral")
        app = App.get_running_app()
        if getattr(app, "root", None) is not None and "login" in app.root.screen_names:
            original_transition = app.root.transition
            app.root.transition = NoTransition()
            app.root.current = "login"
            app.root.transition = original_transition

    def go_login(self) -> None:
        self.open_login()

    def submit_registration(self) -> None:
        if self.submitting:
            return

        payload = {
            "full_name": self.ids.full_name_input.text.strip(),
            "display_name": self.ids.display_name_input.text.strip(),
            "email": self.ids.email_input.text.strip(),
            "confirm_email": self.ids.confirm_email_input.text.strip(),
            "phone": self.ids.phone_input.text.strip(),
            "password": self.ids.password_input.text,
            "confirm_password": self.ids.confirm_password_input.text,
        }

        if not payload["full_name"] or not payload["display_name"] or not payload["email"] or not payload["password"]:
            self.set_feedback("Completa todos los campos obligatorios para crear la cuenta.", "warning")
            return
        if payload["email"].lower() != payload["confirm_email"].lower():
            self.set_feedback("Los correos electronicos no coinciden.", "warning")
            return
        if payload["password"] != payload["confirm_password"]:
            self.set_feedback("Las contrasenas no coinciden.", "warning")
            return

        self.set_feedback("", "neutral")
        self.set_status("Creando cuenta...")
        if self.ids and "register_button" in self.ids:
            self.ids.register_button.begin_action("Creando cuenta...")
        self.submitting = True
        self.load_data(
            "register_submit",
            lambda: self.get_service("auth_api_service").register(payload),
            self._handle_register_success,
            self._handle_register_error,
            loading_message="Creando tu cuenta...",
            use_cached_preview=False,
            show_offline_on_error=False,
        )

    def _handle_register_success(self, payload: dict) -> None:
        self.submitting = False
        if self.ids and "register_button" in self.ids:
            self.ids.register_button.finish_action(flash_tone="success")
        self.clear_form()
        login_screen = App.get_running_app().root.get_screen("login")
        login_screen.set_feedback(payload.get("message", "Cuenta creada correctamente."), "success")
        if login_screen.ids:
            login_screen.ids.email_input.text = payload.get("user", {}).get("email", "")
        App.get_running_app().show_status("Cuenta creada correctamente. Ya puedes iniciar sesion.")

        def go_to_login(_dt) -> None:
            app = App.get_running_app()
            if getattr(app, "root", None) is not None and "login" in app.root.screen_names:
                original_transition = app.root.transition
                app.root.transition = NoTransition()
                app.root.current = "login"
                app.root.transition = original_transition

        Clock.schedule_once(go_to_login, 0.15)

    def _handle_register_error(self, error: Exception) -> None:
        self.submitting = False
        if self.ids and "register_button" in self.ids:
            self.ids.register_button.finish_action(flash_tone="danger")
        if isinstance(error, AuthApiNetworkError):
            self.set_feedback("Servidor no disponible. Intenta nuevamente cuando tengas conexion.", "warning")
            self.set_status("No fue posible conectarse al backend de autenticacion.")
            return

        if isinstance(error, AuthApiServiceError):
            message = "Email ya existe. Usa otro correo o inicia sesion." if error.code == "email_exists" else str(error)
            self.set_feedback(message, "warning" if error.status_code < 500 else "danger")
            self.set_status(message)
            return

        self.set_feedback("No fue posible crear la cuenta.", "danger")
        self.set_status(f"Error inesperado al registrar la cuenta: {error}")

    def clear_form(self) -> None:
        if not self.ids:
            return
        for field_id in (
            "full_name_input",
            "display_name_input",
            "email_input",
            "confirm_email_input",
            "phone_input",
            "password_input",
            "confirm_password_input",
        ):
            self.ids[field_id].text = ""
        self.set_feedback("", "neutral")
