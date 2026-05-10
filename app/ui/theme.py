from __future__ import annotations

import customtkinter as ctk

PRIMARY = "#00C2FF"
SUCCESS = "#22C55E"
DANGER = "#EF4444"
WARNING = "#F59E0B"
SURFACE_DARK = "#0F172A"
SURFACE_LIGHT = "#FFFFFF"
TEXT_DARK = "#0F172A"
TEXT_LIGHT = "#F8FAFC"

COLORS = {
    "app_bg": ("#EEF4FF", "#081120"),
    "surface": (SURFACE_LIGHT, SURFACE_DARK),
    "surface_alt": ("#F7FBFF", "#111827"),
    "sidebar": ("#0F172A", "#020617"),
    "sidebar_hover": "#0E2A40",
    "sidebar_active": "#093247",
    "text_primary": (TEXT_DARK, TEXT_LIGHT),
    "text_secondary": ("#475569", "#94A3B8"),
    "border": ("#D9E2F2", "#1E293B"),
    "primary": PRIMARY,
    "success": SUCCESS,
    "danger": DANGER,
    "warning": WARNING,
    "green": SUCCESS,
    "red": DANGER,
    "blue": PRIMARY,
    "amber": WARNING,
    "cyan": "#0891B2",
    "primary_soft": ("#D8F6FF", "#0C2E38"),
    "success_soft": ("#DCFCE7", "#123024"),
    "danger_soft": ("#FEE2E2", "#341318"),
    "warning_soft": ("#FEF3C7", "#3A2A12"),
}

FONTS = {
    "hero": ("Segoe UI", 30, "bold"),
    "title": ("Segoe UI", 22, "bold"),
    "subtitle": ("Segoe UI", 16, "bold"),
    "body": ("Segoe UI", 14),
    "body_bold": ("Segoe UI", 14, "bold"),
    "small": ("Segoe UI", 12),
    "kpi": ("Segoe UI", 28, "bold"),
}


def tone_palette(tone: str) -> dict[str, str]:
    palettes = {
        "success": {"accent": SUCCESS, "badge": "#DCFCE7", "text": "#14532D"},
        "danger": {"accent": DANGER, "badge": "#FEE2E2", "text": "#7F1D1D"},
        "warning": {"accent": WARNING, "badge": "#FEF3C7", "text": "#78350F"},
        "primary": {"accent": PRIMARY, "badge": "#D8F6FF", "text": "#0C4A5A"},
        "green": {"accent": SUCCESS, "badge": "#DCFCE7", "text": "#14532D"},
        "red": {"accent": DANGER, "badge": "#FEE2E2", "text": "#7F1D1D"},
        "blue": {"accent": PRIMARY, "badge": "#D8F6FF", "text": "#0C4A5A"},
    }
    return palettes.get(tone, palettes["primary"])


def surface_kwargs() -> dict:
    return {
        "fg_color": COLORS["surface"],
        "corner_radius": 20,
        "border_width": 1,
        "border_color": COLORS["border"],
    }


def button_style(variant: str = "primary") -> dict:
    variants = {
        "primary": {
            "fg_color": PRIMARY,
            "hover_color": "#00A9DD",
            "text_color": "#082F49",
        },
        "success": {
            "fg_color": SUCCESS,
            "hover_color": "#16A34A",
            "text_color": "#F8FAFC",
        },
        "danger": {
            "fg_color": DANGER,
            "hover_color": "#DC2626",
            "text_color": "#F8FAFC",
        },
        "warning": {
            "fg_color": WARNING,
            "hover_color": "#D97706",
            "text_color": "#0F172A",
        },
        "secondary": {
            "fg_color": "#1E293B",
            "hover_color": "#334155",
            "text_color": "#F8FAFC",
        },
    }
    style = variants.get(variant, variants["primary"]).copy()
    style.update({"corner_radius": 14, "border_width": 0})
    return style


def chart_colors() -> dict[str, str]:
    dark_mode = ctk.get_appearance_mode().lower() == "dark"
    return {
        "background": "#0F172A" if dark_mode else "#FFFFFF",
        "grid": "#334155" if dark_mode else "#D9E2F2",
        "text": "#E2E8F0" if dark_mode else "#0F172A",
        "bar": PRIMARY,
        "bar_peak": SUCCESS,
    }
