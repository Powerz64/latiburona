from __future__ import annotations

from threading import Thread, current_thread

from kivy.app import App
from kivy.clock import Clock
from kivy.properties import StringProperty
from kivy.uix.screenmanager import NoTransition

from app.services import AuthApiNetworkError, AuthApiServiceError
from kivy_ui.components.loading import hide_loading, show_loading
from kivy_ui.screens.base_screen import ServiceScreen


class LoginScreen(ServiceScreen):
    feedback_text = StringProperty("")
    feedback_tone = StringProperty("neutral")
    helper_text = StringProperty("Ingresa con tu cuenta para sincronizar reservas, reportes y torneos.")

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._login_attempt_id = 0
        self._restore_attempt_id = 0
        self._active_restore_attempt_id: int | None = None
        self._restore_watchdog = None
        self._active_restore_cached_user: dict | None = None
        self.loading = False

    @staticmethod
    def _debug_log(message: str) -> None:
        print(f"[LaTiburona][LoginScreen][{current_thread().name}] {message}")

    def refresh(self) -> None:
        if self.ids:
            session = self.get_service("session_service").load_session()
            if "remember_check" in self.ids:
                self.ids.remember_check.active = True
            if session and session.get("user", {}).get("email") and not self.ids.email_input.text.strip():
                self.ids.email_input.text = session["user"]["email"]
        if not App.get_running_app().is_authenticated:
            self.set_status("Acceso listo. Inicia sesion para continuar.")

    def set_feedback(self, message: str, tone: str = "neutral") -> None:
        self.feedback_text = message
        self.feedback_tone = tone

    def show_loader(self, message: str = "Validando credenciales...") -> None:
        show_loading(self, message)

    def hide_loader(self) -> None:
        hide_loading(self)

    def show_error(self, message: str) -> None:
        tone = "warning" if message in {"Credenciales incorrectas", "Error de conexion"} else "danger"
        self.set_feedback(message, tone)
        if message == "Error de conexion":
            self.set_status("No fue posible conectarse al backend de autenticacion.")
        else:
            self.set_status(message)

    def open_register(self) -> None:
        self.set_feedback("", "neutral")
        app = App.get_running_app()
        if getattr(app, "root", None) is not None and "register" in app.root.screen_names:
            original_transition = app.root.transition
            app.root.transition = NoTransition()
            app.root.current = "register"
            app.root.transition = original_transition

    def go_register(self) -> None:
        self.open_register()

    def forgot_password(self) -> None:
        self.notify(
            "Recuperacion de acceso",
            "Solicita al administrador el restablecimiento de tu contrasena o usa el script local de soporte.",
            tone="primary",
        )

    def login(self) -> None:
        self.submit_login()

    def submit_login(self) -> None:
        if self.loading:
            self._debug_log("Login ignorado porque ya existe una solicitud en curso.")
            return

        email = self.ids.email_input.text.strip()
        password = self.ids.password_input.text
        remember_session = bool(self.ids.remember_check.active) if "remember_check" in self.ids else True

        if not email or not password:
            self.set_feedback("Completa correo y contrasena para continuar.", "warning")
            return

        self.set_feedback("", "neutral")
        self.set_status("Iniciando sesion...")
        self._login_attempt_id += 1
        attempt_id = self._login_attempt_id
        if self.ids and "login_button" in self.ids:
            self.ids.login_button.begin_action("Validando acceso...")
        self.loading = True
        self._debug_log(f"Iniciando login en background. attempt_id={attempt_id}")
        self.show_loader("Validando credenciales...")
        Thread(
            target=self._login_thread,
            args=(attempt_id, email, password, remember_session),
            daemon=True,
        ).start()

    def _login_thread(self, attempt_id: int, email: str, password: str, remember_session: bool) -> None:
        self._debug_log(f"Thread de login activo. attempt_id={attempt_id}")
        try:
            data = self.get_service("auth_api_service").login(email, password)
            token = str(data.get("access_token") or "").strip()
            user = data.get("user", {})
            payload = {
                "access_token": token,
                "user": user,
                "remember_session": remember_session,
            }
            self._schedule_login_success(attempt_id, payload)
        except AuthApiNetworkError as exc:
            self._debug_log(f"Error de red en thread de login. attempt_id={attempt_id} error={exc}")
            self._schedule_login_error(attempt_id, str(exc) or "Error de conexion")
        except AuthApiServiceError as exc:
            self._debug_log(f"Error auth en thread de login. attempt_id={attempt_id} code={exc.code} error={exc}")
            message = "Credenciales incorrectas" if exc.code == "invalid_credentials" else str(exc)
            self._schedule_login_error(attempt_id, message)
        except Exception as exc:
            self._debug_log(f"Error en thread de login. attempt_id={attempt_id} error={exc}")
            message = str(exc).strip() or "Error de conexion"
            self._schedule_login_error(attempt_id, message)

    def _schedule_login_success(self, attempt_id: int, payload: dict) -> None:
        Clock.schedule_once(
            lambda _dt, request_id=attempt_id, result=payload: self._on_login_success(request_id, result)
        )

    def _schedule_login_error(self, attempt_id: int, message: str) -> None:
        Clock.schedule_once(
            lambda _dt, request_id=attempt_id, error_message=message: self._on_login_error(request_id, error_message)
        )

    def restore_saved_session(self) -> None:
        if self.loading:
            self._debug_log("Restauracion ignorada porque ya existe una solicitud en curso.")
            return

        session = self.get_service("session_service").load_session()
        if not session:
            self.set_feedback("", "neutral")
            return

        token = str(session.get("access_token", "")).strip()
        cached_user = session.get("user") if isinstance(session.get("user"), dict) else None
        if not token:
            App.get_running_app().clear_session_state("No encontramos una sesion valida.")
            return

        if cached_user and self.ids and not self.ids.email_input.text.strip():
            self.ids.email_input.text = cached_user.get("email", "")

        self._restore_attempt_id += 1
        attempt_id = self._restore_attempt_id
        self._active_restore_attempt_id = attempt_id
        self._active_restore_cached_user = dict(cached_user or {})
        self.loading = True
        self.set_feedback("Validando sesion guardada...", "primary")
        self.set_status("Validando sesion guardada...")
        print("SESSION RESTORE: validating saved session", flush=True)
        self._debug_log(f"Iniciando restauracion de sesion en background. attempt_id={attempt_id}")
        show_loading(self, "Validando sesion guardada...")
        if self._restore_watchdog is not None:
            self._restore_watchdog.cancel()
            self._restore_watchdog = None
        Thread(
            target=self._restore_thread,
            args=(attempt_id, token),
            daemon=True,
        ).start()
        self._restore_watchdog = Clock.schedule_once(
            lambda _dt, request_id=attempt_id: self._force_restore_timeout(request_id),
            3,
        )

    def _restore_thread(self, attempt_id: int, token: str) -> None:
        callback = self._schedule_restore_fail
        payload = (attempt_id, "No fue posible validar la sesion guardada.")
        callback_name = "error"
        self._debug_log(f"THREAD START restore attempt_id={attempt_id}")

        try:
            user = self.get_service("auth_api_service").me(token)
            callback = self._schedule_restore_success
            callback_name = "success"
            payload = (attempt_id, {"access_token": token, "user": user, "offline": False})
        except AuthApiNetworkError as exc:
            self._debug_log(f"Red no disponible en restauracion. attempt_id={attempt_id} error={exc}")
            cached_user = self._active_restore_cached_user or {}
            if cached_user:
                callback = self._schedule_restore_success
                callback_name = "offline_success"
                payload = (attempt_id, {"access_token": token, "user": cached_user, "offline": True})
            else:
                payload = (attempt_id, str(exc) or "No fue posible validar la sesion guardada.")
        except AuthApiServiceError as exc:
            self._debug_log(f"Error auth en restauracion. attempt_id={attempt_id} code={exc.code} error={exc}")
            if exc.code == "invalid_session":
                payload = (attempt_id, "La sesion guardada vencio. Inicia sesion nuevamente.")
            elif self._active_restore_cached_user:
                callback = self._schedule_restore_success
                callback_name = "cached_success"
                payload = (
                    attempt_id,
                    {
                        "access_token": token,
                        "user": dict(self._active_restore_cached_user),
                        "offline": True,
                    },
                )
            else:
                payload = (attempt_id, str(exc) or "No fue posible validar la sesion guardada.")
        except Exception as exc:
            self._debug_log(f"Error inesperado en restauracion. attempt_id={attempt_id} error={exc}")
            payload = (attempt_id, "No fue posible validar la sesion guardada.")
        finally:
            self._debug_log(f"THREAD END restore attempt_id={attempt_id}")

        self._debug_log(
            f"Programando callback UI de restauracion. attempt_id={attempt_id} callback={callback_name}"
        )
        callback(*payload)

    def _schedule_restore_success(self, attempt_id: int, payload: dict) -> None:
        Clock.schedule_once(
            lambda _dt, request_id=attempt_id, result=payload: self._on_restore_success(request_id, result)
        )

    def _schedule_restore_fail(self, attempt_id: int, message: str) -> None:
        Clock.schedule_once(
            lambda _dt, request_id=attempt_id, error_message=message: self._on_restore_fail(request_id, error_message)
        )

    def _force_restore_timeout(self, attempt_id: int) -> None:
        if self.loading and self._active_restore_attempt_id == attempt_id:
            self._debug_log(f"FORCED TIMEOUT restore attempt_id={attempt_id}")
            self._on_restore_fail(attempt_id, "Tiempo de espera agotado al validar la sesion.")

    def _finish_restore_attempt(self, attempt_id: int) -> bool:
        if attempt_id != self._active_restore_attempt_id:
            return False
        self._active_restore_attempt_id = None
        self._active_restore_cached_user = None
        self.loading = False
        if self._restore_watchdog is not None:
            self._restore_watchdog.cancel()
            self._restore_watchdog = None
        hide_loading(self)
        return True

    def _on_restore_success(self, attempt_id: int, payload: dict) -> None:
        if not self._finish_restore_attempt(attempt_id):
            return
        self._debug_log(f"CALLBACK SUCCESS restore attempt_id={attempt_id}")
        self.set_feedback("", "neutral")
        offline = bool(payload.get("offline"))
        self.set_status("Sesion recuperada en modo offline." if offline else "Sesion validada. Abriendo dashboard...")
        self._complete_login_safe(payload["access_token"], payload["user"], offline=offline, persist_session=True)

    def _on_restore_fail(self, attempt_id: int, message: str) -> None:
        if not self._finish_restore_attempt(attempt_id):
            return
        self._debug_log(f"CALLBACK FAIL restore attempt_id={attempt_id} message={message}")
        tone = "warning" if message in {
            "La sesion guardada vencio. Inicia sesion nuevamente.",
            "Tiempo de espera agotado al validar la sesion.",
            "No fue posible validar la sesion guardada.",
        } else "danger"
        App.get_running_app().clear_session_state(message)
        self.set_feedback(message, tone)

    def _on_login_success(self, attempt_id: int, payload: dict) -> None:
        if attempt_id != self._login_attempt_id:
            return
        self._debug_log(f"Callback success en UI. attempt_id={attempt_id}")
        self.loading = False
        self.hide_loader()
        if self.ids and "login_button" in self.ids:
            self.ids.login_button.finish_action(flash_tone="success")
        if self.ids:
            self.ids.password_input.text = ""
        self.set_status("Acceso validado. Abriendo dashboard...")
        Clock.schedule_once(lambda _dt, result=dict(payload): self._complete_login_safe(result), 0.12)

    def _on_login_error(self, attempt_id: int, message: str) -> None:
        if attempt_id != self._login_attempt_id:
            return
        self._debug_log(f"Callback error en UI. attempt_id={attempt_id} message={message}")
        self.loading = False
        self.hide_loader()
        if self.ids and "login_button" in self.ids:
            self.ids.login_button.finish_action(flash_tone="danger")
        if self.ids:
            self.ids.password_input.text = ""
        self.show_error(message)

    def _complete_login_safe(self, token_or_payload, user: dict | None = None, **kwargs) -> None:
        try:
            App.get_running_app().complete_login(token_or_payload, user, **kwargs)
        except Exception as exc:
            self._debug_log(f"Error completando login en UI: {exc}")
            self.loading = False
            self.hide_loader()
            if self.ids and "login_button" in self.ids:
                self.ids.login_button.finish_action(flash_tone="danger")
            self.set_feedback("No fue posible abrir la sesion. Intenta nuevamente.", "danger")
            self.set_status(f"Error al abrir sesion: {exc}")
