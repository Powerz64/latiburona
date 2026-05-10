from __future__ import annotations

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Line, Rectangle, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.properties import DictProperty, StringProperty
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from kivy_ui.components.cards import HeatmapCell
from kivy_ui.theme import active_theme_hex, rgba


class BarChart(Widget):
    chart_data = DictProperty({})
    highlight_label = StringProperty("")
    title = StringProperty("Reservas por hora")
    x_axis_label = StringProperty("Hora")
    y_axis_label = StringProperty("Cantidad")

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._redraw_event = Clock.create_trigger(self._redraw, -1)
        app = App.get_running_app()
        if app is not None:
            app.bind(theme_mode=lambda *_args: self._queue_redraw())

        self.bind(
            pos=self._queue_redraw,
            size=self._queue_redraw,
            chart_data=self._queue_redraw,
            highlight_label=self._queue_redraw,
        )

    def set_data(self, data: dict[str, int], highlight_label: str = "") -> None:
        self.chart_data = data
        self.highlight_label = highlight_label

    def _queue_redraw(self, *_args) -> None:
        self._redraw_event()

    def _redraw(self, *_args) -> None:
        self.canvas.after.clear()
        if self.width <= dp(200) or self.height <= dp(200):
            return

        theme = active_theme_hex()
        data = self.chart_data or {}
        labels = list(data.keys())
        values = list(data.values())
        has_data = bool(labels) and sum(values) > 0
        max_value = max(max(values, default=0), 1)

        left = self.x + dp(54)
        right = self.right - dp(24)
        bottom = self.y + dp(54)
        top = self.top - dp(44)
        chart_width = max(right - left, 1)
        chart_height = max(top - bottom, 1)
        step_x = chart_width / max(len(labels), 1)
        bar_width = min(step_x * 0.58, dp(28))

        with self.canvas.after:
            Color(*rgba(theme["surface_alt"], 0.9))
            RoundedRectangle(pos=(left, bottom), size=(chart_width, chart_height), radius=[dp(18)])

            if not has_data:
                self._draw_text(self.title, self.center_x, self.top - dp(24), color=rgba(theme["text_primary"]), font_size=15)
                self._draw_text(
                    "Aun no hay suficientes datos para graficar.",
                    self.center_x,
                    self.center_y - dp(8),
                    color=rgba(theme["text_secondary"]),
                    font_size=13,
                )
                self._draw_text(
                    self.x_axis_label,
                    self.center_x,
                    self.y + dp(2),
                    color=rgba(theme["text_muted"]),
                    font_size=11,
                )
                return

            for line_index in range(5):
                y_value = bottom + (chart_height / 4) * line_index
                Color(*rgba(theme["border"], 0.85))
                Line(points=[left, y_value, right, y_value], width=1)
                grid_value = round((max_value / 4) * line_index)
                self._draw_text(
                    str(grid_value),
                    self.x + dp(10),
                    y_value - dp(8),
                    color=rgba(theme["text_muted"]),
                    anchor="left",
                    font_size=11,
                )

            for index, label in enumerate(labels):
                value = values[index]
                bar_height = (value / max_value) * (chart_height - dp(12)) if max_value else 0
                bar_x = left + step_x * index + (step_x - bar_width) / 2
                is_peak = label == self.highlight_label
                color = theme["success"] if is_peak else theme["primary"]
                alpha = 1 if is_peak else 0.45

                Color(*rgba(color, alpha))
                RoundedRectangle(
                    pos=(bar_x, bottom),
                    size=(bar_width, max(bar_height, dp(4))),
                    radius=[dp(10)],
                )

                if value > 0:
                    self._draw_text(
                        str(value),
                        bar_x + (bar_width / 2),
                        bottom + bar_height + dp(6),
                        color=rgba(theme["text_secondary"], 1 if is_peak else 0.62),
                        font_size=11,
                    )

                self._draw_text(
                    label,
                    bar_x + (bar_width / 2),
                    self.y + dp(18),
                    color=rgba(theme["text_muted"], 1 if is_peak else 0.58),
                    font_size=10,
                )

            self._draw_text(self.title, self.center_x, self.top - dp(24), color=rgba(theme["text_primary"]), font_size=15)
            self._draw_text(
                self.x_axis_label,
                self.center_x,
                self.y + dp(2),
                color=rgba(theme["text_muted"]),
                font_size=11,
            )
            self._draw_text(
                self.y_axis_label,
                self.x + dp(8),
                self.top - dp(26),
                color=rgba(theme["text_muted"]),
                anchor="left",
                font_size=11,
            )

    def _draw_text(
        self,
        text: str,
        x: float,
        y: float,
        *,
        color: list[float],
        anchor: str = "center",
        font_size: int = 12,
    ) -> None:
        label = CoreLabel(text=text, font_size=sp(font_size), color=color)
        label.refresh()
        texture = label.texture
        if anchor == "left":
            pos = (x, y)
        else:
            pos = (x - texture.size[0] / 2, y)
        Rectangle(texture=texture, pos=pos, size=texture.size)


class DemandBars(Widget):
    chart_data = DictProperty({})
    peak_label = StringProperty("")

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._redraw_event = Clock.create_trigger(self._redraw, -1)
        app = App.get_running_app()
        if app is not None:
            app.bind(theme_mode=lambda *_args: self._queue_redraw())

        self.bind(
            pos=self._queue_redraw,
            size=self._queue_redraw,
            chart_data=self._queue_redraw,
            peak_label=self._queue_redraw,
        )

    def set_data(self, data: dict[str, int], peak_label: str = "") -> None:
        self.chart_data = data or {}
        self.peak_label = peak_label

    def _queue_redraw(self, *_args) -> None:
        self._redraw_event()

    def _sorted_rows(self) -> list[tuple[str, int]]:
        rows = list((self.chart_data or {}).items())
        rows.sort(key=lambda item: (-item[1], item[0]))
        positive_rows = [item for item in rows if item[1] > 0]
        return positive_rows[:5] if positive_rows else []

    def _redraw(self, *_args) -> None:
        self.canvas.after.clear()
        if self.width <= dp(220) or self.height <= dp(120):
            return

        theme = active_theme_hex()
        rows = self._sorted_rows()

        with self.canvas.after:
            if not rows:
                self._draw_text(
                    "Sin datos aun",
                    self.center_x,
                    self.center_y + dp(8),
                    color=rgba(theme["text_primary"]),
                    font_size=16,
                )
                self._draw_text(
                    "Empieza registrando reservas",
                    self.center_x,
                    self.center_y - dp(18),
                    color=rgba(theme["text_muted"]),
                    font_size=12,
                )
                return

            left = self.x + dp(4)
            right = self.right - dp(4)
            label_width = dp(70)
            count_width = dp(48)
            bar_left = left + label_width
            bar_right = right - count_width
            bar_width = max(bar_right - bar_left, dp(100))
            max_value = max(value for _, value in rows)
            row_gap = dp(14)
            row_height = dp(22)
            total_height = len(rows) * row_height + max(len(rows) - 1, 0) * row_gap
            start_y = self.center_y + total_height / 2 - row_height

            for index, (label, value) in enumerate(rows):
                y = start_y - index * (row_height + row_gap)
                fill_ratio = value / max_value if max_value else 0
                fill_width = max(bar_width * fill_ratio, dp(18))
                is_peak = label == self.peak_label
                fill_color = theme["primary"] if is_peak else theme["surface_soft"]
                soft_color = theme["primary_soft"] if is_peak else theme["surface_soft"]
                label_color = rgba(theme["text_primary"] if is_peak else theme["text_muted"], 1 if is_peak else 0.52)
                value_color = rgba(theme["primary"] if is_peak else theme["text_secondary"], 1 if is_peak else 0.58)
                track_color = rgba(theme["primary_soft"], 0.72 if is_peak else 0.22)

                Color(*track_color)
                RoundedRectangle(
                    pos=(bar_left, y),
                    size=(bar_width, row_height),
                    radius=[dp(11)],
                )
                Color(*rgba(fill_color if fill_ratio >= 0.65 or is_peak else soft_color, 1 if is_peak else 0.56))
                RoundedRectangle(
                    pos=(bar_left, y),
                    size=(fill_width, row_height),
                    radius=[dp(11)],
                )
                if is_peak:
                    Color(*rgba(theme["primary"], 0.18))
                    RoundedRectangle(
                        pos=(bar_left - dp(4), y - dp(4)),
                        size=(bar_width + dp(8), row_height + dp(8)),
                        radius=[dp(13)],
                    )

                self._draw_text(
                    label,
                    left + dp(6),
                    y + dp(2),
                    color=label_color,
                    anchor="left",
                    font_size=11,
                )
                self._draw_text(
                    str(value),
                    right - dp(6),
                    y + dp(2),
                    color=value_color,
                    anchor="right",
                    font_size=11,
                )

    def _draw_text(
        self,
        text: str,
        x: float,
        y: float,
        *,
        color: list[float],
        anchor: str = "center",
        font_size: int = 12,
    ) -> None:
        label = CoreLabel(text=text, font_size=sp(font_size), color=color)
        label.refresh()
        texture = label.texture
        if anchor == "left":
            pos = (x, y)
        elif anchor == "right":
            pos = (x - texture.size[0], y)
        else:
            pos = (x - texture.size[0] / 2, y)
        Rectangle(texture=texture, pos=pos, size=texture.size)


class OccupancyHeatmap(GridLayout):
    chart_data = DictProperty({})

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("cols", 8)
        kwargs.setdefault("spacing", dp(8))
        kwargs.setdefault("size_hint_y", None)
        super().__init__(**kwargs)
        app = App.get_running_app()
        if app is not None:
            app.bind(theme_mode=lambda *_args: self._rebuild())
        self.bind(chart_data=lambda *_args: self._rebuild())

    def set_data(self, data: dict) -> None:
        self.chart_data = data or {}

    def _header_label(self, text: str) -> Label:
        theme = active_theme_hex()
        return Label(
            text=text,
            color=rgba(theme["text_muted"]),
            font_size="10sp",
            bold=True,
            size_hint_y=None,
            height=dp(24),
        )

    def _row_label(self, text: str) -> Label:
        theme = active_theme_hex()
        return Label(
            text=text,
            color=rgba(theme["text_secondary"]),
            font_size="10sp",
            size_hint_y=None,
            height=dp(28),
            text_size=(dp(54), dp(28)),
            halign="right",
            valign="middle",
        )

    def _rebuild(self, *_args) -> None:
        self.clear_widgets()
        data = self.chart_data or {}
        columns = data.get("columns", [])
        rows = data.get("rows", [])
        self.cols = len(columns) + 1 if columns else 1
        row_height = dp(28)
        self.height = row_height * (len(rows) + 1) + dp(6) * max(len(rows), 1)

        self.add_widget(self._header_label("Hora"))
        for column in columns:
            self.add_widget(self._header_label(f"{column['weekday']}\n{column['label']}"))

        for row in rows:
            self.add_widget(self._row_label(row["time"]))
            for cell in row["cells"]:
                widget = HeatmapCell(
                    size_hint_y=None,
                    height=row_height,
                    padding=dp(6),
                    radius=dp(12),
                    shadow_offset=dp(0),
                )
                widget.apply_data(cell["label"], cell["tone"])
                widget.add_widget(
                    Label(
                        text=widget.text,
                        color=widget.text_color,
                        font_size="10sp",
                        bold=True,
                        text_size=(dp(38), dp(20)),
                        halign="center",
                        valign="middle",
                    )
                )
                self.add_widget(widget)
