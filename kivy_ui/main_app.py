from __future__ import annotations

from pathlib import Path
from threading import Thread

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.properties import BooleanProperty, DictProperty, ObjectProperty, StringProperty
from kivy.uix.screenmanager import NoTransition, Screen, ScreenManager

from app.utils.constants import APP_NAME
from kivy_ui.components import (
    ActionButton,
    AppSpinner,
    AppTextInput,
    BaseCard,
    BarChart,
    CardBox,
    DangerButton,
    DemandCard,
    DemandBars,
    DayChipButton,
    FieldCard,
    HeroCard,
    HeroKpiCard,
    InfoCard,
    InfoPill,
    InsightsCard,
    KpiCard,
    LiveOccupancyCard,
    LiveOccupancyRow,
    OccupancyHeatmap,
    PrimaryButton,
    ReservationRow,
    SecondaryButton,
    SidebarButton,
    SlotButton,
    SoftButton,
    SportsHeroCard,
    SportsToggle,
    SuccessButton,
    TournamentRow,
)
from kivy_ui.components.dialogs import show_message
from kivy_ui.components.sidebar import home_screen_for_role, screen_access_for_role, sidebar_items_for_role
from kivy_ui.screens import (
    CalendarScreen,
    DashboardScreen,
    LoginScreen,
    RegisterScreen,
    ReportsScreen,
    ReservationsScreen,
    SettingsScreen,
    TournamentsScreen,
)
from kivy_ui.screens.reservations_screen import FIELDS
from kivy_ui.theme import DEFAULT_THEME_MODE, ThemeState, load_theme_mode, save_theme_mode, theme_rgba

KV_FILES = [
    "components.kv",
    "main.kv",
    "login.kv",
    "register.kv",
    "dashboard.kv",
    "reservations.kv",
    "calendar.kv",
    "reports.kv",
    "tournaments.kv",
    "settings.kv",
]


class ShellScreen(Screen):
    status_text = StringProperty("Sistema listo para operar.")
    offline_banner_visible = BooleanProperty(False)
    offline_banner_text = StringProperty("Sin conexión. Mostrando datos guardados.")
    current_user_text = StringProperty("Sin sesión")
    current_mode_text = StringProperty("Modo oscuro")
    page_title = StringProperty("Tablero")
    page_subtitle = StringProperty("Centro deportivo de reservas, canchas y torneos.")

    page_descriptions = {
        "dashboard": ("⚽ Tablero", "Pulso comercial, canchas destacadas y demanda nocturna."),
        "reservations": ("📅 Reservas", "Partidos, horarios, disponibilidad y control operativo."),
        "calendar": ("🏟 Calendario", "Disponibilidad por cancha, franja y jornada deportiva."),
        "reports": ("📊 Reportes", "Lecturas ejecutivas para ocupacion, ingresos y reservas."),
        "tournaments": ("🏆 Torneos", "Ligas internas, participantes y estados de competencia."),
        "settings": ("⚙️ Configuración", "Tarifas, reglas de ingreso, tema y cuenta activa."),
    }
    screen_registry = (
        ("dashboard", DashboardScreen),
        ("reservations", ReservationsScreen),
        ("calendar", CalendarScreen),
        ("reports", ReportsScreen),
        ("tournaments", TournamentsScreen),
        ("settings", SettingsScreen),
    )

    def __init__(self, **kwargs) -> None:
        self._inner_ready = False
        super().__init__(**kwargs)

    def on_kv_post(self, *_args) -> None:
        self._ensure_inner_screens()
        app = App.get_running_app()
        if app is not None:
            app.bind(current_user=lambda *_args: self._handle_user_change())
        self._render_sidebar()
        self.set_mode_text(App.get_running_app().theme_mode)
        home_screen = self._home_screen()
        self._set_nav_state(home_screen)
        self._set_page_copy(home_screen)

    def _ensure_inner_screens(self) -> None:
        if self._inner_ready:
            return
        for screen_name, screen_class in self.screen_registry:
            if screen_name not in self.ids.inner_sm.screen_names:
                self.ids.inner_sm.add_widget(screen_class(name=screen_name))
        self._inner_ready = True
        print(f"INNER SCREENS: {list(self.ids.inner_sm.screen_names)}", flush=True)

    def set_mode_text(self, mode: str) -> None:
        self.current_mode_text = "Modo oscuro" if mode == "dark" else "Modo claro"

    def _current_role(self) -> str:
        app = App.get_running_app()
        current_user = getattr(app, "current_user", {}) if app is not None else {}
        return str((current_user or {}).get("role", "admin")).strip().lower() or "admin"

    def _home_screen(self) -> str:
        return home_screen_for_role(self._current_role())

    def is_screen_allowed(self, screen_name: str) -> bool:
        return screen_name in screen_access_for_role(self._current_role())

    def _render_sidebar(self) -> None:
        if "nav_list" not in self.ids:
            return
        current_screen = self.ids.inner_sm.current or self._home_screen()
        self.ids.nav_list.clear_widgets()
        for item in sidebar_items_for_role(self._current_role()):
            target = item["screen_name"]
            button = SidebarButton(
                icon_text=item["icon_text"],
                title_text=item["title_text"],
                caption_text=item["caption_text"],
                screen_name=target,
            )
            button.bind(on_release=lambda _instance, destination=target: self.switch_screen(destination))
            self.ids.nav_list.add_widget(button)
        self._set_nav_state(current_screen if self.is_screen_allowed(current_screen) else self._home_screen())

    def _handle_user_change(self) -> None:
        self._render_sidebar()
        target = self.ids.inner_sm.current or self._home_screen()
        if not self.is_screen_allowed(target):
            self.ids.inner_sm.current = self._home_screen()
            target = self.ids.inner_sm.current
        self._set_nav_state(target)
        self._set_page_copy(target)

    def after_login(self, user: dict, offline: bool = False) -> None:
        display_name = user.get("display_name") or user.get("full_name") or "Equipo"
        self.current_user_text = display_name
        self.offline_banner_visible = offline
        if offline:
            self.offline_banner_text = "Sin conexión. Mostrando datos guardados."
        self._ensure_inner_screens()
        self._render_sidebar()
        home_screen = home_screen_for_role(user.get("role"))
        original_transition = self.ids.inner_sm.transition
        self.ids.inner_sm.transition = NoTransition()
        self.ids.inner_sm.current = home_screen
        self.ids.inner_sm.transition = original_transition
        self._set_nav_state(home_screen)
        self._set_page_copy(home_screen)
        screen = self.ids.inner_sm.get_screen(home_screen)
        if hasattr(screen, "on_navigate_to"):
            Clock.schedule_once(lambda _dt: screen.on_navigate_to(), 0.05)

    def switch_screen(self, screen_name: str) -> None:
        self._ensure_inner_screens()
        target = screen_name if screen_name in self.ids.inner_sm.screen_names else self._home_screen()
        if not self.is_screen_allowed(target):
            App.get_running_app().show_status("Acceso restringido")
            show_message("Acceso restringido", "Acceso restringido", tone="warning")
            return
        print(f"NAVIGATE TO: {target}", flush=True)
        if self.ids.inner_sm.current == target:
            return
        self.ids.inner_sm.current = target
        self._set_nav_state(target)
        self._set_page_copy(target)
        screen = self.ids.inner_sm.get_screen(target)
        if hasattr(screen, "on_navigate_to"):
            Clock.schedule_once(lambda _dt: screen.on_navigate_to(), 0.05)

    def _set_page_copy(self, screen_name: str) -> None:
        self.page_title, self.page_subtitle = self.page_descriptions.get(
            screen_name,
            ("⚽ Tablero", "Centro deportivo de LaTiburona."),
        )
        if screen_name == "settings" and self._current_role() != "admin":
            self.page_subtitle = "Reglas de ingreso, tema y cuenta activa."

    def _set_nav_state(self, screen_name: str) -> None:
        if "nav_list" not in self.ids:
            return
        for widget in self.ids.nav_list.children:
            if hasattr(widget, "screen_name"):
                widget.is_active = widget.screen_name == screen_name


class LaTiburonaApp(App):
    services = DictProperty({})
    fields = DictProperty(dict(FIELDS))
    theme = DictProperty({})
    theme_hex = DictProperty({})
    theme_state = ObjectProperty(None, rebind=True)
    theme_mode = StringProperty(DEFAULT_THEME_MODE)
    is_authenticated = BooleanProperty(False)
    current_user = DictProperty({})
    shell_screen = ObjectProperty(None, allownone=True)

    def __init__(self, services: dict, **kwargs) -> None:
        super().__init__(**kwargs)
        self.services = services
        self.theme_mode = load_theme_mode()
        self.theme_state = ThemeState(self.theme_mode)
        self._sync_theme_state()
        self.title = f"{APP_NAME} | Kivy SaaS"
        self._kv_loaded = False

    def build(self):
        print("APP BUILD START", flush=True)
        Window.size = (1500, 930)
        Window.clearcolor = self.theme["app_bg"]
        self._load_kv_files()

        root_manager = ScreenManager(transition=NoTransition())
        root_manager.add_widget(LoginScreen(name="login"))
        root_manager.add_widget(RegisterScreen(name="register"))
        self.shell_screen = ShellScreen(name="shell")
        root_manager.add_widget(self.shell_screen)
        root_manager.current = "login"
        print(f"ROOT SCREENS: {list(root_manager.screen_names)}", flush=True)
        return root_manager

    def _load_kv_files(self) -> None:
        if self._kv_loaded:
            return
        kv_dir = Path(__file__).resolve().parent / "kv"
        for filename in KV_FILES:
            kv_path = kv_dir / filename
            if not kv_path.exists():
                raise FileNotFoundError(f"No se encontro el archivo KV requerido: {kv_path}")
            Builder.unload_file(str(kv_path))
            Builder.load_file(str(kv_path))
        self._kv_loaded = True

    def on_start(self) -> None:
        Clock.schedule_once(lambda _dt: self._bootstrap_auth_flow(), 0.05)

    def _bootstrap_auth_flow(self) -> None:
        if not isinstance(self.root, ScreenManager):
            return
        self.root.current = "login"
        session = self.services["session_service"].load_session()
        login_screen = self.root.get_screen("login")
        if session and session.get("access_token"):
            login_screen.restore_saved_session()
            return
        login_screen.refresh()

    def complete_login(
        self,
        token: str | dict,
        user: dict | None = None,
        *,
        offline: bool = False,
        persist_session: bool = True,
    ) -> None:
        if isinstance(token, dict):
            payload = dict(token)
            token = str(payload.get("access_token") or "").strip()
            user = payload.get("user") if isinstance(payload.get("user"), dict) else {}
            offline = bool(payload.get("offline", offline))
            persist_session = bool(payload.get("remember_session", persist_session))
        if not isinstance(user, dict):
            user = {}
        token = str(token or "").strip()
        if not token:
            print("AUTH RESPONSE: refusing login without token", flush=True)
            self.clear_session_state("Respuesta invalida del servidor: token ausente.", clear_persisted=False)
            return
        if not user:
            print("AUTH RESPONSE: refusing login without user", flush=True)
            self.clear_session_state("Respuesta invalida del servidor: usuario ausente.", clear_persisted=False)
            return

        self.services["api_client"].set_access_token(token)
        self.services["api_client"].reset_error()
        self.current_user = dict(user)
        self.is_authenticated = True
        self.set_offline_banner(offline)
        Thread(
            target=self._persist_session_state,
            args=(token, dict(user), persist_session),
            daemon=True,
        ).start()
        if isinstance(self.root, ScreenManager):
            original_transition = self.root.transition
            self.root.transition = NoTransition()
            self.root.current = "shell"
            self.root.transition = original_transition
        if self.shell_screen is not None:
            Clock.schedule_once(lambda _dt: self.shell_screen.after_login(dict(user), offline), 0)
        self.show_status(
            "Sesión iniciada en modo offline con datos guardados."
            if offline
            else f"Bienvenido, {user.get('display_name', 'equipo')}."
        )

    def _persist_session_state(self, token: str, user: dict, persist_session: bool) -> None:
        try:
            if persist_session:
                self.services["session_service"].save_session(token, user)
            else:
                self.services["session_service"].clear_session()
        except Exception as exc:
            print(f"SESSION PERSIST ERROR: {exc}", flush=True)

    def clear_session_state(self, message: str, *, clear_persisted: bool = True) -> None:
        if clear_persisted:
            self.services["session_service"].clear_session()
        self.services["api_client"].clear_access_token()
        self.is_authenticated = False
        self.current_user = {}
        if self.shell_screen is not None:
            self.shell_screen.current_user_text = "Sin sesión"
            self.shell_screen.offline_banner_visible = False
        if isinstance(self.root, ScreenManager):
            original_transition = self.root.transition
            self.root.transition = NoTransition()
            self.root.current = "login"
            self.root.transition = original_transition
            login_screen = self.root.get_screen("login")
            if hasattr(login_screen, "set_feedback"):
                login_screen.set_feedback(message, "warning" if "expiro" in message.lower() else "neutral")
            login_screen.refresh()

    def logout(self) -> None:
        self.clear_session_state("Sesión cerrada correctamente.")

    def refresh_screens(self, screen_names: list[str] | tuple[str, ...]) -> None:
        shell = self.get_shell_screen()
        if shell is None:
            return
        seen: set[str] = set()
        for index, screen_name in enumerate(screen_names):
            if (
                screen_name in seen
                or screen_name not in shell.ids.inner_sm.screen_names
                or not shell.is_screen_allowed(screen_name)
            ):
                continue
            seen.add(screen_name)
            screen = shell.ids.inner_sm.get_screen(screen_name)
            Clock.schedule_once(
                lambda _dt, target=screen: target.request_load() if hasattr(target, "request_load") else target.refresh(),
                index * 0.04,
            )

    def refresh_all(self) -> None:
        if not isinstance(self.root, ScreenManager):
            return
        if not self.is_authenticated:
            screen = self.root.get_screen(self.root.current)
            if hasattr(screen, "safe_load"):
                screen.safe_load()
            elif hasattr(screen, "refresh"):
                screen.refresh()
            return
        self.refresh_screens(["dashboard", "reservations", "calendar", "reports", "tournaments", "settings"])

    def get_shell_screen(self) -> ShellScreen | None:
        return self.shell_screen

    def get_screen(self, screen_name: str):
        if isinstance(self.root, ScreenManager) and screen_name in self.root.screen_names:
            return self.root.get_screen(screen_name)
        shell = self.get_shell_screen()
        if shell is not None and screen_name in shell.ids.inner_sm.screen_names:
            return shell.ids.inner_sm.get_screen(screen_name)
        return None

    def show_status(self, message: str) -> None:
        if self.shell_screen is not None:
            self.shell_screen.status_text = message

    def set_offline_banner(self, is_visible: bool, message: str | None = None) -> None:
        if self.shell_screen is None:
            return
        self.shell_screen.offline_banner_visible = is_visible
        if message:
            self.shell_screen.offline_banner_text = message
        elif is_visible:
            self.shell_screen.offline_banner_text = "Sin conexión. Mostrando datos guardados."

    def apply_theme_mode(self, mode: str, *, persist: bool = True) -> None:
        target_mode = mode if mode in {"dark", "light"} else DEFAULT_THEME_MODE
        self.theme_state.apply_mode(target_mode)
        self._sync_theme_state()
        self.theme_mode = target_mode
        Window.clearcolor = self.theme["app_bg"]
        print(f"THEME APPLIED: {target_mode}", flush=True)
        if persist:
            save_theme_mode(target_mode)
        if self.shell_screen is not None:
            self.shell_screen.set_mode_text(target_mode)
            self.show_status(
                "Tema visual actualizado a modo oscuro."
                if target_mode == "dark"
                else "Tema visual actualizado a modo claro."
            )
        self._notify_theme_applied()
        self._force_theme_repaint()

    def _sync_theme_state(self) -> None:
        self.theme_hex = self.theme_state.to_hex_map()
        self.theme = theme_rgba(self.theme_state)

    def _notify_theme_applied(self) -> None:
        if not self.root:
            return
        for widget in self.root.walk():
            if hasattr(widget, "on_theme_applied"):
                try:
                    widget.on_theme_applied(self.theme_mode)
                except Exception:
                    pass

    def _force_theme_repaint(self) -> None:
        if not self.root:
            return

        def repaint_tree(_dt=None) -> None:
            for widget in self.root.walk():
                for canvas in (widget.canvas.before, widget.canvas, widget.canvas.after):
                    if hasattr(canvas, "ask_update"):
                        canvas.ask_update()
                if hasattr(widget, "do_layout"):
                    try:
                        widget.do_layout()
                    except Exception:
                        pass
            self.root.canvas.ask_update()

        repaint_tree()
        Clock.schedule_once(repaint_tree, 0)
