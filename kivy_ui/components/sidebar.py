from __future__ import annotations

from kivy.animation import Animation
from kivy.app import App
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior

from kivy_ui.components.cards import CardBox
from kivy_ui.theme import CARD_RADIUS, SPACE_MD, active_theme_hex, rgba

SIDEBAR_ITEMS = (
    {
        "screen_name": "dashboard",
        "icon_text": "⚽",
        "title_text": "Tablero",
        "caption_text": "Pulso del club",
        "roles": ("admin", "operator"),
    },
    {
        "screen_name": "reservations",
        "icon_text": "📅",
        "title_text": "Reservas",
        "caption_text": "Partidos y pagos",
        "roles": ("admin", "operator", "client"),
    },
    {
        "screen_name": "calendar",
        "icon_text": "🏟",
        "title_text": "Calendario",
        "caption_text": "Disponibilidad",
        "roles": ("admin", "operator", "client"),
    },
    {
        "screen_name": "tournaments",
        "icon_text": "🏆",
        "title_text": "Torneos",
        "caption_text": "Ligas y llaves",
        "roles": ("admin", "operator", "client"),
    },
    {
        "screen_name": "reports",
        "icon_text": "📊",
        "title_text": "Reportes",
        "caption_text": "Analitica",
        "roles": ("admin", "operator"),
    },
    {
        "screen_name": "settings",
        "icon_text": "⚙️",
        "title_text": "Configuración",
        "caption_text": "Reglas y cuenta",
        "roles": ("admin", "operator", "client"),
    },
)


def normalize_user_role(role: str | None) -> str:
    return str(role or "admin").strip().lower() or "admin"


def sidebar_items_for_role(role: str | None) -> list[dict[str, str]]:
    normalized_role = normalize_user_role(role)
    resolved_items: list[dict[str, str]] = []
    for item in SIDEBAR_ITEMS:
        if normalized_role not in item["roles"]:
            continue
        resolved_items.append(
            {
                "screen_name": item["screen_name"],
                "icon_text": item["icon_text"],
                "title_text": item["title_text"],
                "caption_text": item["caption_text"],
            }
        )
    return resolved_items


def screen_access_for_role(role: str | None) -> set[str]:
    return {item["screen_name"] for item in sidebar_items_for_role(role)}


def home_screen_for_role(role: str | None) -> str:
    return "reservations" if normalize_user_role(role) == "client" else "dashboard"


class SidebarButton(ButtonBehavior, CardBox):
    icon_text = StringProperty("")
    title_text = StringProperty("")
    caption_text = StringProperty("")
    screen_name = StringProperty("")
    is_active = BooleanProperty(False)
    is_hovered = BooleanProperty(False)
    icon_color = ListProperty(rgba("#E5E7EB"))
    icon_background = ListProperty(rgba("#111827"))
    title_color = ListProperty(rgba("#E5E7EB"))
    caption_color = ListProperty(rgba("#94A3B8"))
    indicator_color = ListProperty(rgba("#00C2FF"))
    motion_progress = NumericProperty(0.0)

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("orientation", "horizontal")
        kwargs.setdefault("padding", [SPACE_MD, dp(10), SPACE_MD, dp(10)])
        kwargs.setdefault("spacing", dp(10))
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(56))
        kwargs.setdefault("radius", CARD_RADIUS)
        super().__init__(**kwargs)

        Window.bind(mouse_pos=self._on_mouse_pos)
        app = App.get_running_app()
        if app is not None:
            app.bind(theme_mode=lambda *_args: self._update_visual_state())

        self.bind(is_active=self._animate_visual_state, is_hovered=self._animate_visual_state)
        self.bind(state=self._animate_visual_state)
        self.bind(motion_progress=self._update_visual_state)
        self._update_visual_state()

    def _on_mouse_pos(self, _window, position) -> None:
        if not self.get_root_window():
            return
        local_x, local_y = self.to_widget(*position)
        hovered = self.collide_point(local_x, local_y)
        if hovered != self.is_hovered:
            self.is_hovered = hovered
            self._set_cursor("hand" if hovered else "arrow")

    @staticmethod
    def _set_cursor(cursor_name: str) -> None:
        try:
            Window.set_system_cursor(cursor_name)
        except Exception:
            return

    def _animate_visual_state(self, *_args) -> None:
        active_like = self.is_active or self.state == "down" or self.is_hovered
        target = 1.0 if active_like else 0.0
        Animation.cancel_all(self, "motion_progress")
        Animation(motion_progress=target, duration=0.18, t="out_quad").start(self)
        self._update_visual_state()

    def _update_visual_state(self, *_args) -> None:
        theme = active_theme_hex()
        lift = max(0.0, min(1.0, float(self.motion_progress)))
        if self.is_active:
            self.background_color = rgba(theme["sidebar_active"])
            self.border_color = rgba(theme["primary"], 0.52 + lift * 0.16)
            self.icon_background = rgba(theme["primary_soft"], 0.98)
            self.icon_color = rgba(theme["primary"])
            self.title_color = rgba(theme["text_primary"])
            self.caption_color = rgba(theme["text_secondary"])
            self.indicator_color = rgba(theme["primary"])
            self.inner_border_color = rgba("#FFFFFF", 0.04)
            self.shadow_color = rgba(theme["primary"], 0.14 + lift * 0.08)
            self.shadow_offset = dp(1 + lift * 2)
        elif self.state == "down" or self.is_hovered:
            self.background_color = rgba(theme["sidebar_hover"])
            self.border_color = rgba(theme["primary"], 0.34 + lift * 0.16)
            self.icon_background = rgba(theme["primary_soft"])
            self.icon_color = rgba(theme["primary"])
            self.title_color = rgba(theme["text_primary"])
            self.caption_color = rgba(theme["text_secondary"])
            self.indicator_color = rgba(theme["primary"], 0.55)
            self.inner_border_color = rgba("#FFFFFF", 0.03)
            self.shadow_color = rgba(theme["primary"], 0.1 + lift * 0.08)
            self.shadow_offset = dp(1 + lift * 1.8)
        else:
            self.background_color = rgba(theme["sidebar"], 0)
            self.border_color = rgba(theme["sidebar"], 0)
            self.icon_background = rgba(theme["surface_alt"])
            self.icon_color = rgba(theme["text_secondary"])
            self.title_color = rgba(theme["text_secondary"])
            self.caption_color = rgba(theme["text_muted"])
            self.indicator_color = rgba(theme["sidebar"], 0)
            self.inner_border_color = rgba("#FFFFFF", 0)
            self.shadow_color = rgba(theme["shadow"], 0)
            self.shadow_offset = dp(0)
