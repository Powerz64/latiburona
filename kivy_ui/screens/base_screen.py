from __future__ import annotations

from threading import Thread

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.properties import BooleanProperty, StringProperty
from kivy.uix.screenmanager import Screen

from app.services.cache_service import load_cache, save_cache
from kivy_ui.components.dialogs import ask_confirmation, show_message


class BaseScreen(Screen):
    loading = BooleanProperty(False)
    loading_message = StringProperty("")
    inline_status = StringProperty("")

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._background_task_versions: dict[str, int] = {}
        self._loading = False
        self._active_tasks = 0
        self._built = False

    def on_kv_post(self, *_args) -> None:
        self._built = True

    def on_enter(self, *_args) -> None:
        print(f"ENTER SCREEN: {self.name}", flush=True)
        self._animate_content_entry()

    def on_leave(self, *_args) -> None:
        print(f"LEAVE SCREEN: {self.name}", flush=True)

    def _animate_content_entry(self) -> None:
        content = self.ids.get("content") if self.ids else None
        if content is None:
            return
        visible_sections = [widget for widget in reversed(content.children) if getattr(widget, "height", 0) > 0]
        for index, widget in enumerate(visible_sections[:10]):
            Animation.cancel_all(widget, "opacity")
            widget.opacity = 0.0
            Clock.schedule_once(
                lambda _dt, target=widget: Animation(opacity=1.0, duration=0.22, t="out_quad").start(target),
                0.025 * index,
            )

    def on_navigate_to(self) -> None:
        self.request_load()

    def request_load(self) -> None:
        if type(self).refresh is not BaseScreen.refresh:
            self.refresh()
            return
        self.safe_load()

    def on_theme_applied(self, _mode: str) -> None:
        """Hook para actualizaciones visuales sin recargar datos."""

    def get_service(self, key: str):
        return App.get_running_app().services[key]

    def get_shell(self):
        app = App.get_running_app()
        return getattr(app, "shell_screen", None)

    def notify(self, title_text: str, message_text: str, tone: str = "primary") -> None:
        show_message(title_text, message_text, tone=tone)

    def confirm_action(
        self,
        title_text: str,
        message_text: str,
        callback,
        *,
        tone: str = "warning",
        confirm_text: str = "Confirmar",
    ) -> None:
        ask_confirmation(
            title_text,
            message_text,
            callback,
            tone=tone,
            confirm_text=confirm_text,
        )

    def set_status(self, message: str) -> None:
        self.inline_status = message
        App.get_running_app().show_status(message)

    def set_offline_banner(self, is_visible: bool) -> None:
        App.get_running_app().set_offline_banner(is_visible)

    def show_inline_loader(self, message: str = "Cargando...") -> None:
        self.loading = True
        self.loading_message = message

    def hide_inline_loader(self) -> None:
        self.loading = False
        self.loading_message = ""

    def fetch_data(self):
        return None

    def apply_data(self, _payload) -> None:
        return None

    def apply_error(self, error: Exception) -> None:
        self.set_status(f"Error: {error}")

    def refresh(self) -> None:
        self.safe_load()

    def safe_load(self) -> None:
        if self._loading:
            return
        self._loading = True
        self.show_inline_loader("Cargando...")
        print(f"LOAD START: {self.name}", flush=True)
        self.run_in_background(
            f"{self.name}_safe_load",
            self.fetch_data,
            self._apply_safe_load_success,
            self._apply_safe_load_error,
        )

    def safe_refresh(self) -> None:
        self.safe_load()

    def _apply_safe_load_success(self, payload) -> None:
        try:
            self.apply_data(payload)
        finally:
            print(f"LOAD END: {self.name}", flush=True)
            self.hide_inline_loader()
            self._loading = False

    def _apply_safe_load_error(self, error: Exception) -> None:
        try:
            self.apply_error(error)
        finally:
            print(f"LOAD END: {self.name}", flush=True)
            self.hide_inline_loader()
            self._loading = False

    def load_data(
        self,
        task_name: str,
        worker,
        on_success=None,
        on_error=None,
        *,
        cache_name: str | None = None,
        loading_message: str = "Cargando datos...",
        use_cached_preview: bool = True,
        show_offline_on_error: bool = True,
        show_loading_overlay: bool = False,
    ) -> None:
        print(f"LOAD START: {self.name}", flush=True)
        cached_payload = load_cache(cache_name) if cache_name and use_cached_preview else None
        has_cached_payload = isinstance(cached_payload, dict)

        if has_cached_payload and on_success:
            Clock.schedule_once(
                lambda _dt, payload=dict(cached_payload): on_success(payload),
                0,
            )
            self.set_status("Mostrando datos guardados mientras sincronizamos...")
        else:
            self.show_inline_loader(loading_message)

        def wrapped_success(payload) -> None:
            if cache_name and isinstance(payload, dict):
                save_cache(cache_name, payload)
            shell = self.get_shell()
            if not getattr(shell, "offline_banner_visible", False):
                self.set_offline_banner(False)
            self.hide_inline_loader()
            print(f"LOAD END: {self.name}", flush=True)
            if on_success:
                on_success(payload)

        def wrapped_error(error: Exception) -> None:
            self.hide_inline_loader()
            if show_offline_on_error:
                self.set_offline_banner(True)
            if has_cached_payload and on_success:
                offline_payload = dict(cached_payload)
                offline_payload["offline_mode"] = True
                on_success(offline_payload)
                self.set_status("Sin conexion: mostrando datos guardados.")
                print(f"LOAD END: {self.name}", flush=True)
                return
            print(f"LOAD END: {self.name}", flush=True)
            if on_error:
                on_error(error)

        self.run_in_background(task_name, worker, wrapped_success, wrapped_error)

    def run_in_background(self, task_name: str, worker, on_success=None, on_error=None) -> None:
        task_version = self._background_task_versions.get(task_name, 0) + 1
        self._background_task_versions[task_name] = task_version
        self._active_tasks += 1

        def job() -> None:
            try:
                result = worker()
            except Exception as exc:
                Clock.schedule_once(
                    lambda _dt, error=exc, version=task_version: self._dispatch_background_error(
                        task_name,
                        version,
                        error,
                        on_error,
                    ),
                    0,
                )
                return

            Clock.schedule_once(
                lambda _dt, payload=result, version=task_version: self._dispatch_background_success(
                    task_name,
                    version,
                    payload,
                    on_success,
                ),
                0,
            )

        Thread(target=job, daemon=True).start()

    def _dispatch_background_success(self, task_name: str, task_version: int, payload, callback) -> None:
        self._active_tasks = max(self._active_tasks - 1, 0)
        if self._background_task_versions.get(task_name) != task_version:
            return
        if callback:
            callback(payload)

    def _dispatch_background_error(self, task_name: str, task_version: int, error: Exception, callback) -> None:
        self._active_tasks = max(self._active_tasks - 1, 0)
        if self._background_task_versions.get(task_name) != task_version:
            return
        if callback:
            callback(error)


ServiceScreen = BaseScreen
