from __future__ import annotations

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import BooleanProperty, DictProperty, ListProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout

from kivy_ui.theme import FONT_KPI, active_theme_hex, rgba, tone_palette

HERO_KPI_FONT = "36sp"


def brighten_color(color: list[float], amount: float = 0.05, *, alpha: float | None = None) -> list[float]:
    base = list(color)
    if len(base) < 4:
        base = base + [1.0] * (4 - len(base))
    return [
        min(base[0] + amount, 1.0),
        min(base[1] + amount, 1.0),
        min(base[2] + amount, 1.0),
        base[3] if alpha is None else alpha,
    ]


class CardBox(BoxLayout):
    background_color = ListProperty(rgba("#111827"))
    border_color = ListProperty(rgba("#334155"))
    shadow_color = ListProperty(rgba("#020617", 0.35))
    inner_border_color = ListProperty([1, 1, 1, 0.05])
    radius = NumericProperty(dp(24))
    border_width = NumericProperty(1.1)
    shadow_offset = NumericProperty(dp(2))

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        with self.canvas.before:
            self._shadow_color = Color(*self.shadow_color)
            self._shadow_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
            self._fill_color = Color(*self.background_color)
            self._fill_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
            self._border_color = Color(*self.border_color)
            self._border_line = Line(rounded_rectangle=(*self.pos, *self.size, self.radius), width=self.border_width)
        with self.canvas.after:
            self._inner_border_tint = Color(*self.inner_border_color)
            self._inner_border_line = Line(rounded_rectangle=(*self.pos, *self.size, self.radius), width=1)

        app = App.get_running_app()
        if app is not None:
            app.bind(theme_mode=lambda *_args: self._update_canvas())

        self.bind(pos=self._update_canvas, size=self._update_canvas)
        self.bind(
            background_color=self._update_canvas,
            border_color=self._update_canvas,
            shadow_color=self._update_canvas,
            inner_border_color=self._update_canvas,
        )
        self.bind(radius=self._update_canvas, border_width=self._update_canvas, shadow_offset=self._update_canvas)
        self._update_canvas()

    def _update_canvas(self, *_args) -> None:
        self._shadow_color.rgba = self.shadow_color
        self._shadow_rect.pos = (self.x + dp(2), self.y - self.shadow_offset)
        self._shadow_rect.size = self.size
        self._shadow_rect.radius = [self.radius]

        self._fill_color.rgba = self.background_color
        self._fill_rect.pos = self.pos
        self._fill_rect.size = self.size
        self._fill_rect.radius = [self.radius]

        self._border_color.rgba = self.border_color
        self._border_line.rounded_rectangle = (*self.pos, *self.size, self.radius)
        self._border_line.width = self.border_width

        inset = dp(1)
        self._inner_border_tint.rgba = self.inner_border_color
        self._inner_border_line.rounded_rectangle = (
            self.x + inset,
            self.y + inset,
            max(self.width - inset * 2, 0),
            max(self.height - inset * 2, 0),
            max(self.radius - inset, 0),
        )
        self._inner_border_line.width = 1


class BaseCard(CardBox):
    is_hovered = BooleanProperty(False)
    is_loading = BooleanProperty(False)
    hover_progress = NumericProperty(0.0)
    image_zoom = NumericProperty(1.0)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._cursor_active = False
        Window.bind(mouse_pos=self._on_mouse_pos)
        self.bind(is_hovered=self._animate_hover_motion)

    def _on_mouse_pos(self, _window, position) -> None:
        if not self.get_root_window():
            return
        local_x, local_y = self.to_widget(*position)
        hovered = self.collide_point(local_x, local_y)
        if hovered != self.is_hovered:
            self.is_hovered = hovered
            self._set_cursor("hand" if hovered else "arrow")

    def _set_cursor(self, cursor_name: str) -> None:
        try:
            Window.set_system_cursor(cursor_name)
            self._cursor_active = cursor_name == "hand"
        except Exception:
            self._cursor_active = cursor_name == "hand"

    def _animate_hover_motion(self, *_args) -> None:
        target_progress = 1.0 if self.is_hovered else 0.0
        target_zoom = 1.035 if self.is_hovered else 1.0
        duration = 0.16 if self.is_hovered else 0.24
        Animation.cancel_all(self, "hover_progress", "image_zoom")
        Animation(
            hover_progress=target_progress,
            image_zoom=target_zoom,
            duration=duration,
            t="out_quad",
        ).start(self)

    def _start_loading_pulse(self, *, min_opacity: float = 0.62, max_opacity: float = 1, duration: float = 0.62) -> None:
        Animation.cancel_all(self, "opacity")
        self.opacity = min_opacity
        pulse = Animation(opacity=max_opacity, duration=duration, t="in_out_sine") + Animation(
            opacity=min_opacity,
            duration=duration,
            t="in_out_sine",
        )
        pulse.repeat = True
        pulse.start(self)

    def stop_loading_state(self) -> None:
        if not self.is_loading:
            Animation.cancel_all(self, "opacity")
            self.opacity = 1
            self._schedule_canvas_refresh()
            return
        self.is_loading = False
        Animation.cancel_all(self, "opacity")
        self.opacity = 1
        self._schedule_canvas_refresh()

    def _schedule_canvas_refresh(self) -> None:
        Clock.schedule_once(lambda _dt: self._refresh_visual_tree(), 0)

    def _refresh_visual_tree(self) -> None:
        for canvas in (self.canvas.before, self.canvas, self.canvas.after):
            if hasattr(canvas, "ask_update"):
                canvas.ask_update()
        if hasattr(self, "do_layout"):
            self.do_layout()
        parent = self.parent
        if parent is not None and hasattr(parent, "do_layout"):
            parent.do_layout()

    def set_loading(self, payload: dict | None = None) -> None:
        raise NotImplementedError

    def set_error(self, message: str) -> None:
        raise NotImplementedError

    def set_data(self, data) -> None:
        raise NotImplementedError


class KpiCard(BaseCard):
    title_text = StringProperty("")
    value_text = StringProperty("--")
    status_text = StringProperty("Sin datos")
    caption_text = StringProperty("")
    trend_text = StringProperty("")
    tone = StringProperty("primary")
    value_font_size = StringProperty(FONT_KPI)
    accent_color = ListProperty(rgba("#00C2FF"))
    badge_color = ListProperty(rgba("#0C3142"))
    badge_text_color = ListProperty(rgba("#A5F3FC"))
    trend_color = ListProperty(rgba("#A5F3FC"))

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        app = App.get_running_app()
        if app is not None:
            app.bind(theme_mode=lambda *_args: self._apply_visual_state())
        self.bind(is_hovered=lambda *_args: self._apply_visual_state())
        self.bind(tone=lambda *_args: self._apply_visual_state())

    def set_data(self, data) -> None:
        payload = dict(data) if isinstance(data, dict) else {"value": data}
        self.stop_loading_state()
        tone = str(payload.get("tone") or self.tone or "primary")
        palette = tone_palette(active_theme_hex(), tone)
        self.title_text = str(payload.get("title", self.title_text or ""))
        self.value_text = str(payload.get("value", self.value_text or "--"))
        self.status_text = str(payload.get("status", self.status_text or "Sin datos"))
        self.caption_text = str(payload.get("caption", self.caption_text or ""))
        self.trend_text = str(payload.get("trend") or self._trend_text(self.status_text, tone))
        self.tone = tone
        self.accent_color = rgba(palette["accent"])
        self.badge_color = rgba(palette["soft"])
        self.badge_text_color = rgba(palette["text"])
        self.trend_color = rgba(palette["accent"])
        self.value_font_size = str(payload.get("font_size") or FONT_KPI)
        self._apply_visual_state()
        self._schedule_canvas_refresh()

    def set_loading(self, payload: dict | None = None) -> None:
        payload = payload or {}
        theme = active_theme_hex()
        self.is_loading = True
        self.title_text = str(payload.get("title") or self.title_text or "")
        self.value_text = "......"
        self.status_text = "..."
        self.caption_text = str(payload.get("caption") or "Actualizando indicador...")
        self.trend_text = "...."
        self.tone = str(payload.get("tone") or "primary")
        self.accent_color = rgba(theme["surface_soft"])
        self.badge_color = rgba(theme["surface_soft"], 0.95)
        self.badge_text_color = rgba(theme["text_muted"])
        self.trend_color = rgba(theme["text_muted"], 0.7)
        self.value_font_size = str(payload.get("font_size") or FONT_KPI)
        self._apply_visual_state()
        self._start_loading_pulse()
        self._schedule_canvas_refresh()

    def set_error(self, message: str) -> None:
        self.set_data(
            {
                "value": "--",
                "status": "Sin conexion",
                "tone": "danger",
                "caption": str(message),
                "trend": "! Error",
            }
        )

    def apply_data(self, title: str, value: str, status: str, tone: str, caption: str) -> None:
        self.set_data(
            {
                "title": title,
                "value": value,
                "status": status,
                "tone": tone,
                "caption": caption,
            }
        )

    def show_loading_state(self, title: str, caption: str, tone: str = "primary") -> None:
        self.set_loading({"title": title, "caption": caption, "tone": tone})

    def _apply_visual_state(self) -> None:
        theme = active_theme_hex()
        palette = tone_palette(theme, self.tone or "primary")
        is_hero = isinstance(self, HeroCard)
        surface = rgba(theme["surface"])
        surface_alt = rgba(theme["surface_alt"])

        if is_hero:
            self.background_color = brighten_color(surface_alt, 0.045 if self.is_hovered else 0.025, alpha=1)
            self.border_color = rgba(palette["accent"], 0.82 if self.is_hovered else 0.62)
            self.shadow_color = rgba(theme["shadow"], 0.46 if self.is_hovered else 0.36)
            self.inner_border_color = rgba("#FFFFFF", 0.12 if self.is_hovered else 0.08)
            self.shadow_offset = dp(5 if self.is_hovered else 3)
        elif self.is_hovered:
            self.background_color = brighten_color(surface_alt, 0.03, alpha=1)
            self.border_color = rgba(palette["accent"], 0.55)
            self.shadow_color = rgba(theme["shadow"], 0.4)
            self.inner_border_color = rgba("#FFFFFF", 0.09)
            self.shadow_offset = dp(4)
        else:
            self.background_color = surface
            self.border_color = rgba(theme["border"])
            self.shadow_color = rgba(theme["shadow"], 0.35)
            self.inner_border_color = rgba("#FFFFFF", 0.05)
            self.shadow_offset = dp(2)

    @staticmethod
    def _trend_text(status: str, tone: str) -> str:
        prefix = {
            "success": "+",
            "danger": "!",
            "warning": "!",
            "primary": "~",
        }.get(tone, "~")
        return f"{prefix} {status}"


class HeroCard(KpiCard):
    def set_data(self, data) -> None:
        payload = dict(data) if isinstance(data, dict) else {"value": data}
        payload.setdefault("font_size", HERO_KPI_FONT)
        super().set_data(payload)

    def set_loading(self, payload: dict | None = None) -> None:
        payload = dict(payload or {})
        payload.setdefault("font_size", HERO_KPI_FONT)
        super().set_loading(payload)


class HeroKpiCard(HeroCard):
    pass


class SportsHeroCard(BaseCard):
    title_text = StringProperty("Reserva tu cancha favorita")
    subtitle_text = StringProperty("Gestiona partidos, horarios y torneos")
    eyebrow_text = StringProperty("LA TIBURONA OPERACION DEPORTIVA")
    meta_text = StringProperty("Noches de estadio | Barranquilla")
    image_source = StringProperty("")
    glow_alpha = NumericProperty(0.1)
    gradient_shift = NumericProperty(0.0)
    particle_shift = NumericProperty(0.0)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        app = App.get_running_app()
        if app is not None:
            app.bind(theme_mode=lambda *_args: self._apply_visual_state())
        self.bind(is_hovered=lambda *_args: self._apply_visual_state())
        self._apply_visual_state()
        Clock.schedule_once(lambda _dt: self._start_ambient_glow(), 0)

    def set_loading(self, payload: dict | None = None) -> None:
        self.is_loading = True
        self._start_loading_pulse(min_opacity=0.76, duration=0.72)

    def set_error(self, message: str) -> None:
        self.stop_loading_state()

    def set_data(self, data) -> None:
        self.stop_loading_state()
        payload = dict(data) if isinstance(data, dict) else {}
        self.title_text = str(payload.get("title", self.title_text))
        self.subtitle_text = str(payload.get("subtitle", self.subtitle_text))
        self.meta_text = str(payload.get("meta", self.meta_text))

    def _apply_visual_state(self) -> None:
        theme = active_theme_hex()
        self.background_color = rgba(theme["surface_alt"], 0.96)
        self.border_color = rgba(theme["success" if self.is_hovered else "primary"], 0.72 if self.is_hovered else 0.46)
        self.shadow_color = rgba(theme["shadow"], 0.5 if self.is_hovered else 0.38)
        self.inner_border_color = rgba("#FFFFFF", 0.14 if self.is_hovered else 0.08)
        self.shadow_offset = dp(7 if self.is_hovered else 4)

    def _start_ambient_glow(self) -> None:
        Animation.cancel_all(self, "glow_alpha", "gradient_shift", "particle_shift")
        pulse = Animation(glow_alpha=0.22, duration=1.7, t="in_out_sine") + Animation(
            glow_alpha=0.09,
            duration=1.7,
            t="in_out_sine",
        )
        pulse.repeat = True
        pulse.start(self)

        self.gradient_shift = 0
        gradient = Animation(gradient_shift=1, duration=5.4, t="in_out_sine") + Animation(
            gradient_shift=0,
            duration=5.4,
            t="in_out_sine",
        )
        gradient.repeat = True
        gradient.start(self)

        self.particle_shift = 0
        particles = Animation(particle_shift=1, duration=6.8, t="in_out_sine") + Animation(
            particle_shift=0,
            duration=6.8,
            t="in_out_sine",
        )
        particles.repeat = True
        particles.start(self)


class FieldCard(BaseCard):
    field_name = StringProperty("")
    address_text = StringProperty("")
    location_text = StringProperty("Barranquilla")
    availability_text = StringProperty("Disponible")
    live_status_text = StringProperty("EN VIVO")
    occupancy_text = StringProperty("Ocupación en vivo")
    slots_text = StringProperty("Cupos listos")
    court_type_text = StringProperty("Futbol 5")
    reference_text = StringProperty("Cerca de puntos clave")
    access_text = StringProperty("Acceso rápido")
    promotion_text = StringProperty("Promo activa")
    schedule_text = StringProperty("Cupos prime")
    occupancy_ratio = NumericProperty(0.0)
    image_source = StringProperty("")
    icon_text = StringProperty("⚽")
    tone = StringProperty("success")
    accent_color = ListProperty(rgba("#39FF14"))
    badge_color = ListProperty(rgba("#123A22"))
    badge_text_color = ListProperty(rgba("#C7FFBC"))
    badge_pulse = NumericProperty(0.0)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        app = App.get_running_app()
        if app is not None:
            app.bind(theme_mode=lambda *_args: self._apply_visual_state())
        self.bind(is_hovered=lambda *_args: self._apply_visual_state())
        self.bind(tone=lambda *_args: self._apply_visual_state())
        self._apply_visual_state()
        Clock.schedule_once(lambda _dt: self._start_badge_pulse(), 0.1)

    def set_loading(self, payload: dict | None = None) -> None:
        self.is_loading = True
        self._start_loading_pulse(min_opacity=0.7, duration=0.7)

    def set_error(self, message: str) -> None:
        self.stop_loading_state()
        self.availability_text = str(message or "Sin datos")
        self.tone = "warning"

    def set_data(self, data) -> None:
        self.stop_loading_state()
        payload = dict(data) if isinstance(data, dict) else {}
        self.field_name = str(payload.get("field_name", self.field_name))
        self.address_text = str(payload.get("address", self.address_text))
        self.location_text = str(payload.get("location", self.location_text))
        self.availability_text = str(payload.get("availability", self.availability_text))
        self.live_status_text = str(payload.get("live_status", self.live_status_text))
        self.occupancy_text = str(payload.get("occupancy", self.occupancy_text))
        self.slots_text = str(payload.get("slots", self.slots_text))
        self.court_type_text = str(payload.get("court_type", self.court_type_text))
        self.reference_text = str(payload.get("reference", self.reference_text))
        self.access_text = str(payload.get("access", self.access_text))
        self.promotion_text = str(payload.get("promotion", self.promotion_text))
        self.schedule_text = str(payload.get("schedule", self.schedule_text))
        self.occupancy_ratio = float(payload.get("occupancy_ratio", self.occupancy_ratio) or 0)
        self.image_source = str(payload.get("image_source", self.image_source))
        self.tone = str(payload.get("tone", self.tone))
        self._apply_visual_state()

    def _apply_visual_state(self) -> None:
        theme = active_theme_hex()
        palette = tone_palette(theme, self.tone or "success")
        self.accent_color = rgba(palette["accent"])
        self.badge_color = rgba(palette["soft"], 0.96)
        self.badge_text_color = rgba(palette["text"])
        self.background_color = brighten_color(rgba(theme["surface_alt"]), 0.025 if self.is_hovered else 0.0, alpha=1)
        self.border_color = rgba(palette["accent"], 0.78 if self.is_hovered else 0.42)
        self.shadow_color = rgba(theme["shadow"], 0.44 if self.is_hovered else 0.32)
        self.inner_border_color = rgba("#FFFFFF", 0.1 if self.is_hovered else 0.055)
        self.shadow_offset = dp(6 if self.is_hovered else 3)

    def _start_badge_pulse(self) -> None:
        Animation.cancel_all(self, "badge_pulse")
        pulse = Animation(badge_pulse=1, duration=1.35, t="in_out_sine") + Animation(
            badge_pulse=0,
            duration=1.35,
            t="in_out_sine",
        )
        pulse.repeat = True
        pulse.start(self)


class LiveOccupancyRow(BoxLayout):
    field_name = StringProperty("")
    status_text = StringProperty("")
    slot_text = StringProperty("")
    occupancy_ratio = NumericProperty(0.0)
    tone = StringProperty("success")
    accent_color = ListProperty(rgba("#39FF14"))
    fill_color = ListProperty(rgba("#13223A"))
    text_color = ListProperty(rgba("#F8FAFC"))

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        app = App.get_running_app()
        if app is not None:
            app.bind(theme_mode=lambda *_args: self._apply_visual_state())
        self.bind(tone=lambda *_args: self._apply_visual_state())
        self._apply_visual_state()

    def _apply_visual_state(self) -> None:
        theme = active_theme_hex()
        palette = tone_palette(theme, self.tone or "success")
        self.accent_color = rgba(palette["accent"])
        self.fill_color = rgba(palette["soft"], 0.8)
        self.text_color = rgba(palette["text"])


class LiveOccupancyCard(BaseCard):
    title_text = StringProperty("Ocupacion live")
    subtitle_text = StringProperty("Pulso de canchas, demanda y cupos disponibles")
    rows_data = ListProperty([])

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        app = App.get_running_app()
        if app is not None:
            app.bind(theme_mode=lambda *_args: self._apply_visual_state())
        self.bind(is_hovered=lambda *_args: self._apply_visual_state())
        self.bind(rows_data=lambda *_args: self._render_rows())
        self._apply_visual_state()

    def on_kv_post(self, *_args) -> None:
        self._render_rows()

    def set_loading(self, payload: dict | None = None) -> None:
        payload = payload or {}
        self.is_loading = True
        self.title_text = str(payload.get("title") or self.title_text)
        self.subtitle_text = str(payload.get("subtitle") or "Sincronizando ocupacion en vivo...")
        self.rows_data = []
        self._start_loading_pulse(min_opacity=0.78, duration=0.7)
        self._render_rows()

    def set_error(self, message: str) -> None:
        self.stop_loading_state()
        self.subtitle_text = str(message)
        self.rows_data = []
        self._render_rows()

    def set_data(self, data) -> None:
        self.stop_loading_state()
        payload = dict(data) if isinstance(data, dict) else {}
        self.title_text = str(payload.get("title", self.title_text))
        self.subtitle_text = str(payload.get("subtitle", self.subtitle_text))
        self.rows_data = list(payload.get("rows", self.rows_data) or [])
        self._render_rows()
        self._apply_visual_state()

    def _render_rows(self) -> None:
        if not self.ids or "live_rows" not in self.ids:
            return
        container = self.ids.live_rows
        container.clear_widgets()
        rows = list(self.rows_data or [])
        if not rows:
            rows = [
                {
                    "field_name": "Sin lecturas live",
                    "status_text": "Esperando datos",
                    "slot_text": "Actualizando",
                    "occupancy_ratio": 0.0,
                    "tone": "neutral",
                }
            ]
        for item in rows[:5]:
            ratio = max(0.0, min(1.0, float(item.get("occupancy_ratio", 0) or 0)))
            container.add_widget(
                LiveOccupancyRow(
                    field_name=str(item.get("field_name", "")),
                    status_text=str(item.get("status_text", "")),
                    slot_text=str(item.get("slot_text", "")),
                    occupancy_ratio=ratio,
                    tone=str(item.get("tone", "success")),
                )
            )

    def _apply_visual_state(self) -> None:
        theme = active_theme_hex()
        self.background_color = brighten_color(rgba(theme["surface_alt"]), 0.022 if self.is_hovered else 0.0, alpha=1)
        self.border_color = rgba(theme["success" if self.is_hovered else "primary"], 0.68 if self.is_hovered else 0.48)
        self.shadow_color = rgba(theme["shadow"], 0.48 if self.is_hovered else 0.36)
        self.inner_border_color = rgba("#FFFFFF", 0.11 if self.is_hovered else 0.065)
        self.shadow_offset = dp(6 if self.is_hovered else 3)


class ReservationCourtCard(ButtonBehavior, BaseCard):
    field_name = StringProperty("")
    location_text = StringProperty("")
    address_text = StringProperty("")
    status_text = StringProperty("Disponible")
    occupancy_text = StringProperty("0% ocupacion")
    slots_text = StringProperty("Cupos listos")
    promotion_text = StringProperty("Promo activa")
    court_type_text = StringProperty("Futbol 5")
    peak_text = StringProperty("Pico --")
    features_text = StringProperty("LED | Parqueadero")
    image_source = StringProperty("")
    tone = StringProperty("primary")
    is_selected = BooleanProperty(False)
    accent_color = ListProperty(rgba("#00C2FF"))
    badge_color = ListProperty(rgba("#06364A"))
    badge_text_color = ListProperty(rgba("#A5F3FC"))
    occupancy_ratio = NumericProperty(0.0)
    on_select = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        app = App.get_running_app()
        if app is not None:
            app.bind(theme_mode=lambda *_args: self._apply_visual_state())
        self.bind(is_hovered=lambda *_args: self._apply_visual_state())
        self.bind(is_selected=lambda *_args: self._apply_visual_state())
        self.bind(tone=lambda *_args: self._apply_visual_state())
        self._apply_visual_state()

    def on_release(self, *_args) -> None:
        if self.on_select:
            self.on_select(self.field_name)

    def on_touch_down(self, touch):
        if self.disabled or not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        touch.grab(self)
        self.state = "down"
        self.is_hovered = True
        return True

    def on_touch_up(self, touch):
        if touch.grab_current is not self:
            return super().on_touch_up(touch)
        touch.ungrab(self)
        self.state = "normal"
        self.on_release()
        return True

    def set_loading(self, payload: dict | None = None) -> None:
        self.is_loading = True
        self._start_loading_pulse(min_opacity=0.74, duration=0.7)

    def set_error(self, message: str) -> None:
        self.stop_loading_state()
        self.status_text = str(message or "Sin datos")
        self.tone = "warning"

    def set_data(self, data) -> None:
        self.stop_loading_state()
        payload = dict(data) if isinstance(data, dict) else {}
        self.field_name = str(payload.get("field_name", self.field_name))
        self.location_text = str(payload.get("location", self.location_text))
        self.address_text = str(payload.get("address", self.address_text))
        self.status_text = str(payload.get("status", self.status_text))
        self.occupancy_text = str(payload.get("occupancy", self.occupancy_text))
        self.slots_text = str(payload.get("slots", self.slots_text))
        self.promotion_text = str(payload.get("promotion", self.promotion_text))
        self.court_type_text = str(payload.get("court_type", self.court_type_text))
        self.peak_text = str(payload.get("peak", self.peak_text))
        self.features_text = str(payload.get("features", self.features_text))
        self.image_source = str(payload.get("image_source", self.image_source))
        self.occupancy_ratio = max(0.0, min(1.0, float(payload.get("occupancy_ratio", self.occupancy_ratio) or 0)))
        self.tone = str(payload.get("tone", self.tone))
        self.is_selected = bool(payload.get("is_selected", self.is_selected))
        self._apply_visual_state()

    def _apply_visual_state(self) -> None:
        theme = active_theme_hex()
        palette = tone_palette(theme, self.tone or "primary")
        self.accent_color = rgba(theme["success"] if self.is_selected else palette["accent"])
        self.badge_color = rgba(theme["success_soft"] if self.is_selected else palette["soft"], 0.96)
        self.badge_text_color = rgba("#C7FFBC" if self.is_selected else palette["text"])
        glow = 0.055 if self.is_selected else 0.03 if self.is_hovered else 0.0
        self.background_color = brighten_color(rgba(theme["surface_alt"]), glow, alpha=1)
        self.border_color = rgba(theme["success"] if self.is_selected else palette["accent"], 0.92 if self.is_selected else 0.68 if self.is_hovered else 0.38)
        self.shadow_color = rgba(theme["success"] if self.is_selected else theme["shadow"], 0.30 if self.is_selected else 0.42 if self.is_hovered else 0.30)
        self.inner_border_color = rgba("#FFFFFF", 0.13 if self.is_selected else 0.09 if self.is_hovered else 0.055)
        self.shadow_offset = dp(7 if self.is_selected else 5 if self.is_hovered else 2)


class SportsToggle(ButtonBehavior, CardBox):
    active = BooleanProperty(False)
    label_text = StringProperty("")
    active_text = StringProperty("ON")
    inactive_text = StringProperty("NO")
    knob_color = ListProperty(rgba("#39FF14"))
    track_color = ListProperty(rgba("#123A22"))
    text_color = ListProperty(rgba("#C7FFBC"))
    knob_progress = NumericProperty(0.0)
    glow_alpha = NumericProperty(0.0)

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("orientation", "horizontal")
        kwargs.setdefault("padding", [dp(5), dp(5)])
        kwargs.setdefault("spacing", dp(0))
        super().__init__(**kwargs)
        app = App.get_running_app()
        if app is not None:
            app.bind(theme_mode=lambda *_args: self._apply_visual_state())
        self.knob_progress = 1.0 if self.active else 0.0
        self.bind(active=self._on_active_changed)
        self.bind(state=lambda *_args: self._apply_visual_state())
        self._apply_visual_state()

    def on_release(self) -> None:
        self.active = not self.active

    def _on_active_changed(self, *_args) -> None:
        self._apply_visual_state()
        Animation.cancel_all(self, "knob_progress", "glow_alpha")
        target = 1.0 if self.active else 0.0
        (
            Animation(knob_progress=target, glow_alpha=0.26 if self.active else 0.12, duration=0.16, t="out_quad")
            + Animation(glow_alpha=0.0, duration=0.28, t="out_quad")
        ).start(self)

    def _apply_visual_state(self) -> None:
        theme = active_theme_hex()
        if self.active:
            self.track_color = rgba(theme["success_soft"], 0.95)
            self.knob_color = rgba(theme["success"])
            self.text_color = rgba("#06140B")
            self.border_color = rgba(theme["success"], 0.72)
            self.shadow_color = rgba(theme["success"], 0.2)
        else:
            self.track_color = rgba(theme["surface_soft"], 0.95)
            self.knob_color = rgba(theme["text_muted"], 0.75)
            self.text_color = rgba(theme["text_secondary"])
            self.border_color = rgba(theme["border"], 0.75)
            self.shadow_color = rgba(theme["shadow"], 0.2)
        self.background_color = self.track_color
        self.inner_border_color = rgba("#FFFFFF", 0.05)
        self.shadow_offset = dp(1)


class InsightsCard(BaseCard):
    eyebrow_text = StringProperty("")
    title_text = StringProperty("")
    body_text = StringProperty("")
    badge_text = StringProperty("")
    icon_text = StringProperty("i")
    tone = StringProperty("neutral")
    highlighted = BooleanProperty(False)
    accent_color = ListProperty(rgba("#94A3B8"))
    badge_color = ListProperty(rgba("#1E293B"))
    badge_text_color = ListProperty(rgba("#CBD5E1"))

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        app = App.get_running_app()
        if app is not None:
            app.bind(theme_mode=lambda *_args: self._apply_visual_state())
        self.bind(is_hovered=lambda *_args: self._apply_visual_state())
        self.bind(highlighted=lambda *_args: self._apply_visual_state())
        self.bind(tone=lambda *_args: self._apply_visual_state())
        self._apply_visual_state()

    def set_data(self, data) -> None:
        payload = dict(data) if isinstance(data, dict) else {"body": data}
        self.stop_loading_state()
        tone = str(payload.get("tone") or self.tone or "neutral")
        palette = tone_palette(active_theme_hex(), tone)
        self.eyebrow_text = str(payload.get("eyebrow") or self.eyebrow_text or "")
        self.title_text = str(payload.get("title") or self.title_text or "")
        self.body_text = str(payload.get("body") or self.body_text or "")
        self.badge_text = str(payload.get("badge") or self.badge_text or "")
        self.icon_text = str(payload.get("icon") or self.icon_text or "i")
        self.tone = tone
        self.highlighted = bool(payload.get("highlighted", self.highlighted))
        self.accent_color = rgba(palette["accent"])
        self.badge_color = rgba(palette["soft"])
        self.badge_text_color = rgba(palette["text"])
        self._apply_visual_state()
        self._schedule_canvas_refresh()

    def set_loading(self, payload: dict | None = None) -> None:
        payload = payload or {}
        theme = active_theme_hex()
        self.is_loading = True
        self.eyebrow_text = str(payload.get("eyebrow") or self.eyebrow_text or "")
        self.title_text = str(payload.get("title") or self.title_text or "")
        self.body_text = str(payload.get("body") or "Cargando...")
        self.badge_text = str(payload.get("badge") or "")
        self.icon_text = str(payload.get("icon") or "i")
        self.tone = str(payload.get("tone") or "neutral")
        self.highlighted = bool(payload.get("highlighted", False))
        self.accent_color = rgba(theme["surface_soft"])
        self.badge_color = rgba(theme["surface_soft"], 0.95)
        self.badge_text_color = rgba(theme["text_muted"])
        self._apply_visual_state()
        self._start_loading_pulse(min_opacity=0.68, duration=0.65)
        self._schedule_canvas_refresh()

    def set_error(self, message: str) -> None:
        self.set_data(
            {
                "title": self.title_text or "Sin datos",
                "body": str(message),
                "eyebrow": "Sin respuesta",
                "badge": "Error",
                "icon": self.icon_text or "i",
                "tone": "danger",
                "highlighted": self.highlighted,
            }
        )

    def apply_data(
        self,
        title: str,
        body: str,
        *,
        eyebrow: str = "",
        badge: str = "",
        icon: str = "i",
        tone: str = "neutral",
        highlighted: bool = False,
    ) -> None:
        self.set_data(
            {
                "title": title,
                "body": body,
                "eyebrow": eyebrow,
                "badge": badge,
                "icon": icon,
                "tone": tone,
                "highlighted": highlighted,
            }
        )

    def show_loading_state(
        self,
        title: str,
        body: str,
        *,
        eyebrow: str = "",
        badge: str = "",
        icon: str = "i",
        tone: str = "neutral",
        highlighted: bool = False,
    ) -> None:
        self.set_loading(
            {
                "title": title,
                "body": body,
                "eyebrow": eyebrow,
                "badge": badge,
                "icon": icon,
                "tone": tone,
                "highlighted": highlighted,
            }
        )

    def _apply_visual_state(self) -> None:
        theme = active_theme_hex()
        palette = tone_palette(theme, self.tone or "neutral")
        if self.highlighted:
            self.border_color = rgba(palette["accent"], 0.8)
            self.background_color = brighten_color(rgba(theme["surface_alt"]), 0.025 if self.is_hovered else 0.015, alpha=1)
            self.shadow_color = rgba(theme["shadow"], 0.38 if self.is_hovered else 0.34)
            self.inner_border_color = rgba("#FFFFFF", 0.09 if self.is_hovered else 0.07)
        elif self.is_hovered:
            self.border_color = rgba(palette["accent"], 0.42)
            self.background_color = brighten_color(rgba(theme["surface_alt"]), 0.03, alpha=1)
            self.shadow_color = rgba(theme["shadow"], 0.34)
            self.inner_border_color = rgba("#FFFFFF", 0.08)
        else:
            self.border_color = rgba(theme["border"])
            self.background_color = rgba(theme["surface"])
            self.shadow_color = rgba(theme["shadow"], 0.35)
            self.inner_border_color = rgba("#FFFFFF", 0.05)


class InfoCard(InsightsCard):
    pass


class InfoPill(CardBox):
    text = StringProperty("")


class DemandCard(BaseCard):
    title_text = StringProperty("Demanda por hora")
    subtitle_text = StringProperty("Identifica tus picos operativos")
    peak_text = StringProperty("Hora pico detectada: --")
    summary_text = StringProperty("Sin datos aun")
    peak_label = StringProperty("")
    chart_data = DictProperty({})

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        app = App.get_running_app()
        if app is not None:
            app.bind(theme_mode=lambda *_args: self._apply_visual_state())
        self.bind(is_hovered=lambda *_args: self._apply_visual_state())
        self._apply_visual_state()

    def on_kv_post(self, *_args) -> None:
        if "demand_bars" in self.ids:
            self.ids.demand_bars.set_data({}, "")

    def set_loading(self, payload: dict | None = None) -> None:
        payload = payload or {}
        self.is_loading = True
        self.title_text = str(payload.get("title") or "Demanda por hora")
        self.subtitle_text = str(payload.get("subtitle") or "Identifica tus picos operativos")
        self.peak_label = ""
        self.peak_text = str(payload.get("peak_text") or "Hora pico detectada: --")
        self.summary_text = str(payload.get("summary") or "Sincronizando lectura operativa...")
        self.chart_data = {}
        if "demand_bars" in self.ids:
            self.ids.demand_bars.set_data({}, "")
        self._apply_visual_state()
        self._start_loading_pulse(min_opacity=0.74, duration=0.72)
        self._schedule_canvas_refresh()

    def set_error(self, message: str) -> None:
        self.stop_loading_state()
        self.peak_label = ""
        self.peak_text = "Hora pico detectada: --"
        self.summary_text = str(message)
        self.chart_data = {}
        if "demand_bars" in self.ids:
            self.ids.demand_bars.set_data({}, "")
        self._apply_visual_state()
        self._schedule_canvas_refresh()

    def set_data(self, data) -> None:
        payload = dict(data) if isinstance(data, dict) else {"summary": data}
        self.stop_loading_state()
        self.title_text = str(payload.get("title") or "Demanda por hora")
        self.subtitle_text = str(payload.get("subtitle") or "Identifica tus picos operativos")
        self.peak_label = str(payload.get("peak_label") or "")
        self.peak_text = str(payload.get("peak_text") or f"Hora pico detectada: {self.peak_label or '--'}")
        self.summary_text = str(payload.get("summary") or "Sin datos aun")
        self.chart_data = dict(payload.get("chart_data") or {})
        if "demand_bars" in self.ids:
            self.ids.demand_bars.set_data(self.chart_data, self.peak_label)
        self._apply_visual_state()
        self._schedule_canvas_refresh()

    def _apply_visual_state(self) -> None:
        theme = active_theme_hex()
        if self.is_hovered:
            self.border_color = rgba(theme["primary"], 0.38)
            self.background_color = brighten_color(rgba(theme["surface_alt"]), 0.03, alpha=1)
            self.shadow_color = rgba(theme["shadow"], 0.34)
            self.inner_border_color = rgba("#FFFFFF", 0.08)
        else:
            self.border_color = rgba(theme["border"])
            self.background_color = rgba(theme["surface"])
            self.shadow_color = rgba(theme["shadow"], 0.35)
            self.inner_border_color = rgba("#FFFFFF", 0.05)


class HeatmapCell(CardBox):
    text = StringProperty("0")
    tone = StringProperty("neutral")
    accent_color = ListProperty(rgba("#94A3B8"))
    text_color = ListProperty(rgba("#CBD5E1"))

    def apply_data(self, label: str, tone: str) -> None:
        palette = tone_palette(active_theme_hex(), tone)
        self.text = label
        self.tone = tone
        self.accent_color = rgba(palette["accent"])
        self.text_color = rgba(palette["text"])
        self.background_color = rgba(palette["soft"])
        self.border_color = rgba(palette["accent"], 0.6 if tone != "neutral" else 0.25)
