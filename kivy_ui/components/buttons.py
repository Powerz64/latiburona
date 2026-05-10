from __future__ import annotations

from kivy.animation import Animation
from kivy.app import App
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.graphics import Color, Line, PopMatrix, PushMatrix, Rotate, RoundedRectangle, Scale
from kivy.metrics import dp
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.uix.button import Button

from kivy_ui.theme import UI_FONT, active_theme_hex, button_palette, rgba


class SoftButton(Button):
    variant = StringProperty("primary")
    radius = NumericProperty(dp(18))
    is_hovered = BooleanProperty(False)
    scale_factor = NumericProperty(1.0)
    busy = BooleanProperty(False)
    busy_text = StringProperty("Procesando...")
    spinner_angle = NumericProperty(0)

    def __init__(self, **kwargs) -> None:
        self._idle_text = ""
        self._idle_variant = ""
        self._disabled_before_busy = False
        self._pulse_restore = None
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        kwargs.setdefault("background_color", (0, 0, 0, 0))
        kwargs.setdefault("border", (0, 0, 0, 0))
        kwargs.setdefault("font_name", UI_FONT)
        kwargs.setdefault("font_size", "14sp")
        super().__init__(**kwargs)

        with self.canvas.before:
            PushMatrix()
            self._scale = Scale(1, 1, 1, origin=self.center)
            self._fill_color = Color(0, 0, 0, 0)
            self._fill_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
            self._border_color = Color(0, 0, 0, 0)
            self._border_line = Line(rounded_rectangle=(*self.pos, *self.size, self.radius), width=1.1)
        with self.canvas.after:
            PopMatrix()
            PushMatrix()
            self._spinner_rotate = Rotate()
            self._spinner_color = Color(0, 0, 0, 0)
            self._spinner_arc = Line(width=dp(2.2))
            PopMatrix()

        Window.bind(mouse_pos=self._on_mouse_pos)
        app = App.get_running_app()
        if app is not None:
            app.bind(theme_mode=lambda *_args: self._update_canvas())

        self.bind(pos=self._update_canvas, size=self._update_canvas)
        self.bind(
            state=self._update_canvas,
            disabled=self._update_canvas,
            variant=self._update_canvas,
            radius=self._update_canvas,
            is_hovered=self._update_canvas,
            busy=self._on_busy_changed,
        )
        self.bind(pos=self._sync_transform, size=self._sync_transform, scale_factor=self._sync_transform)
        self.bind(spinner_angle=self._update_spinner)
        self._update_canvas()
        self._sync_transform()
        self._update_spinner()

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

    def _update_canvas(self, *_args) -> None:
        theme = active_theme_hex()
        palette = button_palette(theme, self.variant)
        pressed = self.state == "down" and not self.disabled
        inset = dp(1.2) if pressed else 0
        if self.disabled:
            fill = rgba(theme["surface_soft"], 0.55)
            border = rgba(theme["border"], 0.4)
            text = rgba(theme["text_muted"])
        else:
            if pressed:
                fill = rgba(palette["down"])
            elif self.is_hovered:
                fill = rgba(palette["hover"])
            else:
                fill = rgba(palette["normal"])
            border = rgba(palette["border"])
            text = rgba(palette["text"])

        self._fill_color.rgba = fill
        self._fill_rect.pos = (self.x + inset, self.y + inset)
        self._fill_rect.size = (max(self.width - inset * 2, 0), max(self.height - inset * 2, 0))
        self._fill_rect.radius = [self.radius]
        self._border_color.rgba = border
        self._border_line.rounded_rectangle = (
            self.x + inset,
            self.y + inset,
            max(self.width - inset * 2, 0),
            max(self.height - inset * 2, 0),
            self.radius,
        )
        self._border_line.width = 1.1
        self.color = text
        self.opacity = 0.96 if pressed else 1
        self._animate_press_scale(pressed)

    def _sync_transform(self, *_args) -> None:
        self._scale.origin = self.center
        self._scale.x = self.scale_factor
        self._scale.y = self.scale_factor

    def _animate_press_scale(self, pressed: bool) -> None:
        target = 0.97 if pressed else 1.025 if self.is_hovered and not self.disabled and not self.busy else 1.0
        if abs(self.scale_factor - target) < 0.001:
            return
        Animation.cancel_all(self, "scale_factor")
        Animation(scale_factor=target, duration=0.12 if pressed else 0.18, t="out_quad").start(self)

    def begin_action(self, busy_text: str | None = None) -> None:
        if busy_text:
            self.busy_text = busy_text
        if not self.busy:
            self._idle_text = self.text
            self._idle_variant = self.variant
            self._disabled_before_busy = self.disabled
        self.busy = True

    def finish_action(self, *, flash_tone: str | None = None, restore_text: str | None = None) -> None:
        if self.busy:
            self.busy = False
        if restore_text is not None:
            self.text = restore_text
            self._idle_text = restore_text
        if flash_tone:
            self.flash_feedback(flash_tone)

    def flash_feedback(self, tone: str = "success", duration: float = 0.8) -> None:
        if self._pulse_restore is not None:
            self._pulse_restore.cancel()
            self._pulse_restore = None

        original_variant = self.variant
        self.variant = tone
        Animation.cancel_all(self, "scale_factor")
        (
            Animation(scale_factor=1.05, duration=0.11, t="out_quad")
            + Animation(scale_factor=1.0, duration=0.2, t="out_back")
        ).start(self)

        def restore_variant(_dt) -> None:
            self.variant = self._idle_variant or original_variant
            self._pulse_restore = None

        self._pulse_restore = Clock.schedule_once(restore_variant, duration)

    def _on_busy_changed(self, *_args) -> None:
        if self.busy:
            if not self._idle_text:
                self._idle_text = self.text
            self.text = self.busy_text or self.text
            self.disabled = True
            Animation.cancel_all(self, "spinner_angle")
            spin = Animation(spinner_angle=360, duration=0.85)
            spin.repeat = True
            spin.start(self)
        else:
            Animation.cancel_all(self, "spinner_angle")
            self.spinner_angle = 0
            self.text = self._idle_text or self.text
            self.disabled = self._disabled_before_busy
        self._update_spinner()
        self._update_canvas()

    def _update_spinner(self, *_args) -> None:
        if not hasattr(self, "_spinner_arc"):
            return
        theme = active_theme_hex()
        spinner_visible = self.busy
        spinner_color = button_palette(theme, self.variant)["text"] if spinner_visible else "#000000"
        self._spinner_color.rgba = rgba(spinner_color, 1 if spinner_visible else 0)
        radius = dp(8)
        center_x = self.x + dp(20)
        center_y = self.center_y
        self._spinner_rotate.origin = (center_x, center_y)
        self._spinner_rotate.angle = self.spinner_angle
        self._spinner_arc.circle = (center_x, center_y, radius, 30, 300)


class ActionButton(SoftButton):
    pass


class PrimaryButton(SoftButton):
    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("variant", "primary")
        super().__init__(**kwargs)


class SecondaryButton(SoftButton):
    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("variant", "secondary")
        super().__init__(**kwargs)


class SuccessButton(SoftButton):
    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("variant", "success")
        super().__init__(**kwargs)


class DangerButton(SoftButton):
    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("variant", "danger")
        super().__init__(**kwargs)


class DayChipButton(SoftButton):
    is_active = BooleanProperty(False)

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("variant", "ghost")
        kwargs.setdefault("font_size", "13sp")
        super().__init__(**kwargs)

        self.bind(is_active=self._update_canvas)
        self._update_canvas()

    def _update_canvas(self, *_args) -> None:
        theme = active_theme_hex()
        text = rgba(theme["text_primary"])

        if self.is_active:
            fill = rgba(theme["primary_soft"])
            border = rgba(theme["primary"], 0.9)
            text = rgba(theme["text_primary"])
        elif self.state == "down":
            fill = rgba(theme["surface_alt"])
            border = rgba(theme["primary"], 0.45)
        elif self.is_hovered:
            fill = rgba(theme["surface_alt"])
            border = rgba(theme["border"])
        else:
            fill = rgba(theme["surface"])
            border = rgba(theme["border"])

        self._fill_color.rgba = fill
        self._fill_rect.pos = self.pos
        self._fill_rect.size = self.size
        self._fill_rect.radius = [self.radius]
        self._border_color.rgba = border
        self._border_line.rounded_rectangle = (*self.pos, *self.size, self.radius)
        self._border_line.width = 1.1
        self.color = text


class SlotButton(SoftButton):
    slot_time = StringProperty("")
    slot_status = StringProperty("available")
    is_selected = BooleanProperty(False)

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("variant", "ghost")
        kwargs.setdefault("font_size", "13sp")
        kwargs.setdefault("radius", dp(16))
        super().__init__(**kwargs)

        self.bind(slot_status=self._update_canvas, is_selected=self._update_canvas)
        self._update_canvas()

    def _update_canvas(self, *_args) -> None:
        theme = active_theme_hex()
        palettes = {
            "available": {
                "fill": theme["success_soft"],
                "border": theme["success"],
                "text": theme["success"],
            },
            "partial": {
                "fill": theme["warning_soft"],
                "border": theme["warning"],
                "text": theme["warning"],
            },
            "occupied": {
                "fill": theme["danger_soft"],
                "border": theme["danger"],
                "text": theme["danger"],
            },
        }
        palette = palettes.get(self.slot_status, palettes["available"])

        if self.is_selected:
            fill = rgba(theme["primary"])
            border = rgba(theme["primary"])
            text = rgba("#082032")
        elif self.state == "down" and not self.disabled:
            fill = rgba(palette["border"], 0.92)
            border = rgba(palette["border"])
            text = rgba(theme["surface"])
        elif self.is_hovered and not self.disabled:
            fill = rgba(palette["fill"], 0.95)
            border = rgba(palette["border"], 0.95)
            text = rgba(palette["text"])
        else:
            fill = rgba(palette["fill"])
            border = rgba(palette["border"], 0.88)
            text = rgba(palette["text"])

        self._fill_color.rgba = fill
        self._fill_rect.pos = self.pos
        self._fill_rect.size = self.size
        self._fill_rect.radius = [self.radius]
        self._border_color.rgba = border
        self._border_line.rounded_rectangle = (*self.pos, *self.size, self.radius)
        self._border_line.width = 1.1
        self.color = text
