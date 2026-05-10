from __future__ import annotations

from kivy.app import App
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import ListProperty, NumericProperty
from kivy.uix.spinner import Spinner, SpinnerOption
from kivy.uix.textinput import TextInput

from kivy_ui.theme import UI_FONT, active_theme_hex, rgba


class AppSpinnerOption(SpinnerOption):
    def __init__(self, **kwargs) -> None:
        theme = active_theme_hex()
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_color", rgba(theme["surface_alt"]))
        kwargs.setdefault("color", rgba(theme["text_primary"]))
        kwargs.setdefault("font_name", UI_FONT)
        kwargs.setdefault("font_size", "14sp")
        super().__init__(**kwargs)


class AppTextInput(TextInput):
    fill_color = ListProperty(rgba("#0B1220"))
    border_color = ListProperty(rgba("#2A3A54"))
    focus_color = ListProperty(rgba("#00C2FF"))
    radius = NumericProperty(dp(18))

    def __init__(self, **kwargs) -> None:
        theme = active_theme_hex()
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_active", "")
        kwargs.setdefault("background_color", (0, 0, 0, 0))
        kwargs.setdefault("foreground_color", rgba(theme["text_primary"]))
        kwargs.setdefault("hint_text_color", rgba(theme["text_muted"]))
        kwargs.setdefault("cursor_color", rgba(theme["primary"]))
        kwargs.setdefault("font_name", UI_FONT)
        kwargs.setdefault("padding", [dp(16), dp(15), dp(16), dp(15)])
        kwargs.setdefault("font_size", "14sp")
        super().__init__(**kwargs)

        with self.canvas.before:
            self._fill = Color(*self.fill_color)
            self._fill_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
            self._border = Color(*self.border_color)
            self._border_line = Line(rounded_rectangle=(*self.pos, *self.size, self.radius), width=1.15)

        app = App.get_running_app()
        if app is not None:
            app.bind(theme_mode=lambda *_args: self._apply_theme_tokens())

        self.bind(pos=self._update_canvas, size=self._update_canvas, focus=self._update_canvas)
        self.bind(fill_color=self._update_canvas, border_color=self._update_canvas, focus_color=self._update_canvas)
        self.bind(radius=self._update_canvas)
        self._apply_theme_tokens()
        self._update_canvas()

    def _apply_theme_tokens(self) -> None:
        theme = active_theme_hex()
        self.fill_color = rgba(theme["input_bg"])
        self.border_color = rgba(theme["input_border"])
        self.focus_color = rgba(theme["primary"])
        self.foreground_color = rgba(theme["text_primary"])
        self.hint_text_color = rgba(theme["text_muted"])
        self.cursor_color = rgba(theme["primary"])
        self._update_canvas()

    def _update_canvas(self, *_args) -> None:
        self._fill.rgba = self.fill_color
        self._fill_rect.pos = self.pos
        self._fill_rect.size = self.size
        self._fill_rect.radius = [self.radius]
        self._border.rgba = self.focus_color if self.focus else self.border_color
        self._border_line.rounded_rectangle = (*self.pos, *self.size, self.radius)


class AppSpinner(Spinner):
    fill_color = ListProperty(rgba("#0B1220"))
    border_color = ListProperty(rgba("#2A3A54"))
    focus_color = ListProperty(rgba("#00C2FF"))
    radius = NumericProperty(dp(18))

    def __init__(self, **kwargs) -> None:
        theme = active_theme_hex()
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        kwargs.setdefault("background_color", (0, 0, 0, 0))
        kwargs.setdefault("color", rgba(theme["text_primary"]))
        kwargs.setdefault("font_name", UI_FONT)
        kwargs.setdefault("font_size", "14sp")
        kwargs.setdefault("option_cls", AppSpinnerOption)
        super().__init__(**kwargs)

        with self.canvas.before:
            self._fill = Color(*self.fill_color)
            self._fill_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
            self._border = Color(*self.border_color)
            self._border_line = Line(rounded_rectangle=(*self.pos, *self.size, self.radius), width=1.15)

        app = App.get_running_app()
        if app is not None:
            app.bind(theme_mode=lambda *_args: self._apply_theme_tokens())

        self.bind(pos=self._update_canvas, size=self._update_canvas, state=self._update_canvas)
        self.bind(fill_color=self._update_canvas, border_color=self._update_canvas, focus_color=self._update_canvas)
        self.bind(radius=self._update_canvas)
        self._apply_theme_tokens()
        self._update_canvas()

    def _apply_theme_tokens(self) -> None:
        theme = active_theme_hex()
        self.fill_color = rgba(theme["input_bg"])
        self.border_color = rgba(theme["input_border"])
        self.focus_color = rgba(theme["primary"])
        self.color = rgba(theme["text_primary"])
        self._update_canvas()

    def _update_canvas(self, *_args) -> None:
        self._fill.rgba = self.fill_color
        self._fill_rect.pos = self.pos
        self._fill_rect.size = self.size
        self._fill_rect.radius = [self.radius]
        self._border.rgba = self.focus_color if self.state == "down" else self.border_color
        self._border_line.rounded_rectangle = (*self.pos, *self.size, self.radius)
