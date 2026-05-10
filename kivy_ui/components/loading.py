from __future__ import annotations

from kivy.animation import Animation
from kivy.app import App
from kivy.graphics import Color, Line, PopMatrix, PushMatrix, Rectangle, Rotate, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import NumericProperty, StringProperty
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from kivy_ui.theme import active_theme_hex, theme_rgba


def _theme() -> dict:
    app = App.get_running_app()
    if app and getattr(app, "theme", None):
        return app.theme
    return theme_rgba(active_theme_hex())


class LoadingSpinner(Widget):
    angle = NumericProperty(0)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (dp(68), dp(68))
        with self.canvas:
            PushMatrix()
            self._rotate = Rotate()
            Color(*_theme()["primary"])
            self._arc = Line(width=dp(4))
            PopMatrix()
        self.bind(pos=self._update_canvas, size=self._update_canvas, angle=self._update_canvas)
        self._spin_animation = Animation(angle=360, duration=1.0)
        self._spin_animation.repeat = True
        self._spin_animation.start(self)
        self._update_canvas()

    def _update_canvas(self, *_args) -> None:
        radius = min(self.width, self.height) * 0.34
        self._rotate.origin = self.center
        self._rotate.angle = self.angle
        self._arc.circle = (self.center_x, self.center_y, radius, 18, 300)


class SkeletonBar(Widget):
    tone_alpha = NumericProperty(0.42)
    shimmer_x = NumericProperty(-0.35)

    def __init__(self, *, width_hint: float = 1.0, **kwargs) -> None:
        super().__init__(**kwargs)
        self.size_hint = (width_hint, None)
        self.height = dp(12)
        with self.canvas.before:
            self._color = Color(*self._resolved_color())
            self._shape = RoundedRectangle(radius=[dp(8)])
            self._highlight_color = Color(*self._highlight_rgba())
            self._highlight_shape = RoundedRectangle(radius=[dp(8)])
        self.bind(pos=self._update_canvas, size=self._update_canvas, tone_alpha=self._update_color)
        self.bind(shimmer_x=self._update_canvas)
        self._pulse = Animation(tone_alpha=0.72, duration=0.75) + Animation(tone_alpha=0.32, duration=0.75)
        self._pulse.repeat = True
        self._pulse.start(self)
        self._shimmer = Animation(shimmer_x=1.18, duration=1.15, t="out_quad")
        self._shimmer.repeat = True
        self._shimmer.start(self)
        self._update_canvas()

    def _resolved_color(self) -> list[float]:
        color = list(_theme()["surface_soft"])
        color[-1] = self.tone_alpha
        return color

    def _update_canvas(self, *_args) -> None:
        self._shape.pos = self.pos
        self._shape.size = self.size
        highlight_width = max(self.width * 0.26, dp(28))
        self._highlight_shape.pos = (self.x + self.width * self.shimmer_x, self.y)
        self._highlight_shape.size = (highlight_width, self.height)
        self._update_color()

    def _update_color(self, *_args) -> None:
        self._color.rgba = self._resolved_color()
        self._highlight_color.rgba = self._highlight_rgba()

    def _highlight_rgba(self) -> list[float]:
        theme = _theme()
        color = list(theme["primary"])
        color[-1] = 0.18
        return color


class LoadingPanel(BoxLayout):
    message_text = StringProperty("Cargando datos...")

    def __init__(self, message_text: str = "Cargando datos...", **kwargs) -> None:
        super().__init__(orientation="vertical", spacing=dp(16), padding=dp(22), **kwargs)
        self.size_hint = (None, None)
        self.width = dp(360)
        self.height = dp(244)
        self.message_text = message_text
        with self.canvas.before:
            self._bg_color = Color(*_theme()["surface"])
            self._bg_shape = RoundedRectangle(radius=[dp(24)])
            self._border_color = Color(*_theme()["border"])
            self._border_shape = Line(width=1.1, rounded_rectangle=(0, 0, 0, 0, dp(24)))
        self.bind(pos=self._update_canvas, size=self._update_canvas)

        header = Label(
            text="Sincronizando informacion",
            color=_theme()["text_primary"],
            font_size="18sp",
            bold=True,
            size_hint=(1, None),
            height=dp(24),
            text_size=(self.width - dp(44), dp(24)),
            halign="left",
            valign="middle",
        )
        self.add_widget(header)

        spinner_row = BoxLayout(
            orientation="horizontal",
            spacing=dp(16),
            size_hint=(1, None),
            height=dp(74),
        )
        spinner_row.add_widget(LoadingSpinner())
        message = Label(
            text=self.message_text,
            color=_theme()["text_secondary"],
            font_size="13sp",
            text_size=(dp(220), None),
            halign="left",
            valign="middle",
        )
        self.bind(message_text=lambda *_args: setattr(message, "text", self.message_text))
        spinner_row.add_widget(message)
        self.add_widget(spinner_row)

        skeleton_box = BoxLayout(
            orientation="vertical",
            spacing=dp(10),
            size_hint=(1, None),
            height=dp(86),
        )
        skeleton_box.add_widget(SkeletonBar(width_hint=1.0))
        skeleton_box.add_widget(SkeletonBar(width_hint=0.82))
        skeleton_box.add_widget(SkeletonBar(width_hint=0.66))
        skeleton_box.add_widget(SkeletonBar(width_hint=0.92))
        self.add_widget(skeleton_box)
        self._update_canvas()

    def _update_canvas(self, *_args) -> None:
        self._bg_shape.pos = self.pos
        self._bg_shape.size = self.size
        self._border_shape.rounded_rectangle = (
            self.x,
            self.y,
            self.width,
            self.height,
            dp(24),
        )

    def set_message(self, message_text: str) -> None:
        self.message_text = message_text


class LoadingOverlay(FloatLayout):
    def __init__(self, message_text: str = "Cargando datos...", **kwargs) -> None:
        super().__init__(**kwargs)
        self.size_hint = (1, 1)
        with self.canvas.before:
            self._overlay_color = Color(0.02, 0.05, 0.11, 0.72)
            self._overlay_rect = Rectangle()
        self.bind(pos=self._update_overlay, size=self._update_overlay)
        self._update_overlay()

        anchor = AnchorLayout(anchor_x="center", anchor_y="center")
        self.panel = LoadingPanel(message_text=message_text)
        anchor.add_widget(self.panel)
        self.add_widget(anchor)

    def _update_overlay(self, *_args) -> None:
        self._overlay_rect.pos = self.pos
        self._overlay_rect.size = self.size

    def set_message(self, message_text: str) -> None:
        self.panel.set_message(message_text)

    def on_touch_down(self, touch):
        super().on_touch_down(touch)
        return True

    def on_touch_move(self, touch):
        super().on_touch_move(touch)
        return True

    def on_touch_up(self, touch):
        super().on_touch_up(touch)
        return True


def show_loading(widget, message_text: str = "Cargando datos...") -> None:
    overlay = getattr(widget, "_loading_overlay", None)
    if overlay is None:
        overlay = LoadingOverlay(message_text=message_text)
        widget._loading_overlay = overlay
    else:
        overlay.set_message(message_text)
    if overlay.parent is None:
        widget.add_widget(overlay)


def hide_loading(widget) -> None:
    overlay = getattr(widget, "_loading_overlay", None)
    if overlay is not None and overlay.parent is not None:
        overlay.parent.remove_widget(overlay)
    if overlay is not None:
        widget._loading_overlay = None
