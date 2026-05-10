from __future__ import annotations

import json
from pathlib import Path

from kivy.app import App
from kivy.event import EventDispatcher
from kivy.metrics import dp
from kivy.properties import StringProperty
from kivy.utils import get_color_from_hex

from app.utils.paths import BASE_DIR

DARK_BG = "#07111F"
DARK_SIDEBAR = "#040A14"
DARK_CARD = "#0F172A"
DARK_CARD_2 = "#13223A"
DARK_TEXT = "#F8FAFC"
DARK_MUTED = "#9FB1C7"

LIGHT_BG = "#F1F5F9"
LIGHT_SIDEBAR = "#FFFFFF"
LIGHT_CARD = "#FFFFFF"
LIGHT_CARD_2 = "#E2E8F0"
LIGHT_TEXT = "#0F172A"
LIGHT_MUTED = "#64748B"

ACCENT = "#00C2FF"
SUCCESS = "#39FF14"
WARNING = "#FFD166"
DANGER = "#FF4D5E"

SPACE_XS = dp(8)
SPACE_SM = dp(12)
SPACE_MD = dp(16)
SPACE_LG = dp(24)
SPACE_XL = dp(32)

CARD_RADIUS = dp(22)
SIDEBAR_WIDTH = dp(250)
MAX_CONTENT_WIDTH = dp(1160)

FONT_TITLE = "20sp"
FONT_KPI = "32sp"
FONT_LABEL = "12sp"
FONT_BODY = "14sp"

UI_FONT_PATH = Path(BASE_DIR) / "assets" / "fonts" / "Inter-Regular.ttf"
FALLBACK_UI_FONT_PATH = Path("C:/Windows/Fonts/segoeui.ttf")
UI_FONT = str(UI_FONT_PATH if UI_FONT_PATH.exists() else FALLBACK_UI_FONT_PATH)

EMOJI_FONT_PATH = Path("C:/Windows/Fonts/seguiemj.ttf")
EMOJI_FONT = str(EMOJI_FONT_PATH) if EMOJI_FONT_PATH.exists() else ""


def asset_path(*parts: str) -> str:
    return str(Path(BASE_DIR).joinpath("assets", *parts))


FIELD_IMAGES = {
    "hero": asset_path("images", "fields", "hero_stadium.png"),
    "la_jaula": asset_path("images", "fields", "la_jaula.png"),
    "brazuca": asset_path("images", "fields", "brazuca_soccer.png"),
    "brasileirao": asset_path("images", "fields", "brasileirao.png"),
    "castellana": asset_path("images", "fields", "la_castellana.png"),
    "soccer_house": asset_path("images", "fields", "soccer_house.png"),
}

DARK_THEME = {
    "app_bg": DARK_BG,
    "sidebar": DARK_SIDEBAR,
    "sidebar_hover": "#082033",
    "sidebar_active": "#063247",
    "surface": DARK_CARD,
    "surface_alt": DARK_CARD_2,
    "surface_soft": "#1A2D46",
    "border": "#284563",
    "text_primary": DARK_TEXT,
    "text_secondary": "#D7E6F5",
    "text_muted": DARK_MUTED,
    "primary": ACCENT,
    "success": SUCCESS,
    "warning": WARNING,
    "danger": DANGER,
    "primary_soft": "#06364A",
    "success_soft": "#123A22",
    "warning_soft": "#3B3317",
    "danger_soft": "#421722",
    "input_bg": "#0A1424",
    "input_border": "#33516E",
    "shadow": "#000711",
}

LIGHT_THEME = {
    "app_bg": LIGHT_BG,
    "sidebar": LIGHT_SIDEBAR,
    "sidebar_hover": "#F8FAFC",
    "sidebar_active": "#D8F4FF",
    "surface": LIGHT_CARD,
    "surface_alt": LIGHT_CARD_2,
    "surface_soft": "#E2E8F0",
    "border": "#CBD5E1",
    "text_primary": LIGHT_TEXT,
    "text_secondary": "#334155",
    "text_muted": LIGHT_MUTED,
    "primary": ACCENT,
    "success": SUCCESS,
    "warning": WARNING,
    "danger": DANGER,
    "primary_soft": "#D9F7FF",
    "success_soft": "#DCFCE7",
    "warning_soft": "#FEF3C7",
    "danger_soft": "#FEE2E2",
    "input_bg": "#FFFFFF",
    "input_border": "#CBD5E1",
    "shadow": "#94A3B8",
}

THEME_FIELDS = (
    "app_bg",
    "sidebar",
    "sidebar_hover",
    "sidebar_active",
    "surface",
    "surface_alt",
    "surface_soft",
    "border",
    "text_primary",
    "text_secondary",
    "text_muted",
    "primary",
    "success",
    "warning",
    "danger",
    "primary_soft",
    "success_soft",
    "warning_soft",
    "danger_soft",
    "input_bg",
    "input_border",
    "shadow",
)

THEMES = {
    "dark": DARK_THEME,
    "light": LIGHT_THEME,
}

DEFAULT_THEME_MODE = "dark"
UI_PREFERENCES_PATH = Path(BASE_DIR) / ".latiburona_ui.json"


class ThemeState(EventDispatcher):
    mode = StringProperty(DEFAULT_THEME_MODE)

    app_bg = StringProperty(DARK_BG)
    sidebar = StringProperty(DARK_SIDEBAR)
    sidebar_hover = StringProperty("#0F172A")
    sidebar_active = StringProperty("#082F49")
    surface = StringProperty(DARK_CARD)
    surface_alt = StringProperty(DARK_CARD_2)
    surface_soft = StringProperty("#162033")
    border = StringProperty("#334155")
    text_primary = StringProperty(DARK_TEXT)
    text_secondary = StringProperty("#E2E8F0")
    text_muted = StringProperty(DARK_MUTED)
    primary = StringProperty(ACCENT)
    success = StringProperty(SUCCESS)
    warning = StringProperty(WARNING)
    danger = StringProperty(DANGER)
    primary_soft = StringProperty("#0A3647")
    success_soft = StringProperty("#10281C")
    warning_soft = StringProperty("#3B2A10")
    danger_soft = StringProperty("#3B161C")
    input_bg = StringProperty("#0F172A")
    input_border = StringProperty("#334155")
    shadow = StringProperty("#020617")

    # Compatibility aliases used by existing components.
    bg = StringProperty(DARK_BG)
    card = StringProperty(DARK_CARD)
    card_alt = StringProperty(DARK_CARD_2)
    card_soft = StringProperty("#162033")
    accent = StringProperty(ACCENT)
    text = StringProperty(DARK_TEXT)
    secondary = StringProperty("#E2E8F0")
    muted = StringProperty(DARK_MUTED)

    def __init__(self, mode: str = DEFAULT_THEME_MODE, **kwargs) -> None:
        super().__init__(**kwargs)
        self.apply_mode(mode)

    def apply_mode(self, mode: str) -> None:
        resolved_mode = mode if mode in THEMES else DEFAULT_THEME_MODE
        palette = theme_for_mode(resolved_mode)
        self.mode = resolved_mode
        for field_name in THEME_FIELDS:
            setattr(self, field_name, palette[field_name])
        self.bg = self.app_bg
        self.card = self.surface
        self.card_alt = self.surface_alt
        self.card_soft = self.surface_soft
        self.accent = self.primary
        self.text = self.text_primary
        self.secondary = self.text_secondary
        self.muted = self.text_muted

    def to_hex_map(self) -> dict[str, str]:
        return {field_name: getattr(self, field_name) for field_name in THEME_FIELDS}

    def __getitem__(self, key: str) -> list[float]:
        if hasattr(self, key):
            return rgba(getattr(self, key))
        raise KeyError(key)


def rgba(hex_color: str, alpha: float = 1.0) -> list[float]:
    color = get_color_from_hex(hex_color)
    color[-1] = alpha
    return color


def theme_rgba(theme: dict[str, str] | ThemeState) -> dict[str, list[float]]:
    if isinstance(theme, ThemeState):
        return {field_name: rgba(getattr(theme, field_name)) for field_name in THEME_FIELDS}
    return {field_name: rgba(value) for field_name, value in theme.items()}


def theme_for_mode(mode: str) -> dict[str, str]:
    return THEMES.get(mode, THEMES[DEFAULT_THEME_MODE])


def active_theme_hex() -> dict[str, str]:
    app = App.get_running_app()
    if app and getattr(app, "theme_state", None):
        return app.theme_state.to_hex_map()
    return theme_for_mode(DEFAULT_THEME_MODE)


def tone_palette(theme: dict[str, str], tone: str) -> dict[str, str]:
    palettes = {
        "success": {
            "accent": theme["success"],
            "soft": theme["success_soft"],
            "text": "#C7FFBC" if theme == DARK_THEME else "#166534",
        },
        "danger": {
            "accent": theme["danger"],
            "soft": theme["danger_soft"],
            "text": "#FECACA" if theme == DARK_THEME else "#991B1B",
        },
        "warning": {
            "accent": theme["warning"],
            "soft": theme["warning_soft"],
            "text": "#FFE8A3" if theme == DARK_THEME else "#92400E",
        },
        "primary": {
            "accent": theme["primary"],
            "soft": theme["primary_soft"],
            "text": "#A5F3FC" if theme == DARK_THEME else "#0E7490",
        },
        "neutral": {
            "accent": theme["text_muted"],
            "soft": theme["surface_soft"],
            "text": theme["text_secondary"],
        },
    }
    return palettes.get(tone, palettes["primary"])


def button_palette(theme: dict[str, str], variant: str) -> dict[str, str]:
    variants = {
        "primary": {
            "normal": theme["primary"],
            "hover": "#48D8FF",
            "down": "#009ED1",
            "text": "#04111F",
            "border": theme["primary"],
        },
        "success": {
            "normal": theme["success"],
            "hover": "#6DFF52",
            "down": "#27CC0D",
            "text": "#06140B",
            "border": theme["success"],
        },
        "danger": {
            "normal": theme["danger"],
            "hover": "#F76666",
            "down": "#DC2626",
            "text": "#F8FAFC",
            "border": theme["danger"],
        },
        "warning": {
            "normal": theme["warning"],
            "hover": "#F8B84E",
            "down": "#D97706",
            "text": "#111827",
            "border": theme["warning"],
        },
        "secondary": {
            "normal": theme["surface_soft"],
            "hover": "#173653" if theme == DARK_THEME else theme["surface_alt"],
            "down": theme["surface_alt"],
            "text": theme["text_primary"],
            "border": theme["border"],
        },
        "ghost": {
            "normal": theme["surface"],
            "hover": theme["surface_alt"],
            "down": theme["surface_soft"],
            "text": theme["text_secondary"],
            "border": theme["border"],
        },
    }
    return variants.get(variant, variants["primary"])


def load_ui_preferences() -> dict:
    if not UI_PREFERENCES_PATH.exists():
        return {}
    try:
        return json.loads(UI_PREFERENCES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_ui_preferences(preferences: dict) -> None:
    try:
        UI_PREFERENCES_PATH.write_text(
            json.dumps(preferences, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
    except OSError:
        return


def load_theme_mode() -> str:
    preferences = load_ui_preferences()
    mode = str(preferences.get("theme_mode", DEFAULT_THEME_MODE)).lower()
    return mode if mode in THEMES else DEFAULT_THEME_MODE


def save_theme_mode(mode: str) -> None:
    preferences = load_ui_preferences()
    preferences["theme_mode"] = mode if mode in THEMES else DEFAULT_THEME_MODE
    save_ui_preferences(preferences)
