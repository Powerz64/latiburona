import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from app.ui.components import KPICard, SurfaceCard
from app.ui.theme import COLORS, FONTS, chart_colors
from app.utils.constants import LOCATION_INFO, SCHEDULE_LABELS
from app.utils.formatters import format_currency


class DashboardView(ctk.CTkFrame):
    def __init__(self, parent, controller, analytics_service, settings_service) -> None:
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.analytics_service = analytics_service
        self.settings_service = settings_service

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.kpi_cards: dict[str, KPICard] = {}
        self.insight_var = ctk.StringVar(value="Esperando datos operativos...")
        self.insights_list_var = ctk.StringVar(value="")
        self.recommendations_var = ctk.StringVar(value="")
        self.context_var = ctk.StringVar(value="")

        self._build_kpis()
        self._build_chart_card()
        self._build_insights_card()
        self._build_recommendations_card()
        self._build_context_card()

    def _build_kpis(self) -> None:
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=0, column=0, columnspan=3, sticky="ew", padx=12, pady=(12, 10))
        for index in range(4):
            container.grid_columnconfigure(index, weight=1)

        for index, (key, title) in enumerate(
            [
                ("total_reservations", "Total reservas"),
                ("total_revenue", "Ingresos"),
                ("occupancy_rate", "Ocupacion"),
                ("most_requested_hour", "Hora pico"),
            ]
        ):
            card = KPICard(container, title)
            card.grid(row=0, column=index, sticky="nsew", padx=8)
            self.kpi_cards[key] = card

    def _build_chart_card(self) -> None:
        chart_card = SurfaceCard(self)
        chart_card.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=12, pady=(0, 10))
        chart_card.grid_rowconfigure(1, weight=1)
        chart_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            chart_card,
            text="Dashboard de demanda por hora",
            font=FONTS["title"],
            text_color=COLORS["text_primary"],
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(18, 10))

        self.figure = Figure(figsize=(10, 4.8), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=chart_card)
        self.canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 10))

        insight_box = ctk.CTkFrame(chart_card, fg_color=COLORS["surface_alt"], corner_radius=16)
        insight_box.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 18))
        insight_box.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            insight_box,
            text="Insight destacado",
            font=FONTS["subtitle"],
            text_color=COLORS["text_primary"],
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(
            insight_box,
            textvariable=self.insight_var,
            justify="left",
            wraplength=980,
            font=FONTS["body"],
            text_color=COLORS["text_secondary"],
        ).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 14))

    def _build_insights_card(self) -> None:
        panel = SurfaceCard(self)
        panel.grid(row=2, column=0, sticky="nsew", padx=(12, 8), pady=(0, 12))
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(panel, text="Insights automaticos", font=FONTS["title"]).grid(
            row=0, column=0, sticky="w", padx=18, pady=(18, 10)
        )
        ctk.CTkLabel(
            panel,
            textvariable=self.insights_list_var,
            justify="left",
            wraplength=360,
            font=FONTS["body"],
            text_color=COLORS["text_secondary"],
        ).grid(row=1, column=0, sticky="nw", padx=18, pady=(0, 18))

    def _build_recommendations_card(self) -> None:
        panel = SurfaceCard(self)
        panel.grid(row=2, column=1, sticky="nsew", padx=8, pady=(0, 12))
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(panel, text="Recomendaciones", font=FONTS["title"]).grid(
            row=0, column=0, sticky="w", padx=18, pady=(18, 10)
        )
        ctk.CTkLabel(
            panel,
            textvariable=self.recommendations_var,
            justify="left",
            wraplength=360,
            font=FONTS["body"],
            text_color=COLORS["text_secondary"],
        ).grid(row=1, column=0, sticky="nw", padx=18, pady=(0, 18))

    def _build_context_card(self) -> None:
        panel = SurfaceCard(self)
        panel.grid(row=2, column=2, sticky="nsew", padx=(8, 12), pady=(0, 12))
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(panel, text="Contexto operativo", font=FONTS["title"]).grid(
            row=0, column=0, sticky="w", padx=18, pady=(18, 10)
        )
        ctk.CTkLabel(
            panel,
            textvariable=self.context_var,
            justify="left",
            wraplength=360,
            font=FONTS["body"],
            text_color=COLORS["text_secondary"],
        ).grid(row=1, column=0, sticky="nw", padx=18, pady=(0, 18))

    def refresh_data(self) -> None:
        metrics = self.analytics_service.get_dashboard_metrics()
        settings = self.settings_service.load_settings()

        self.kpi_cards["total_reservations"].update_card(
            str(metrics["kpis"]["total_reservations"]["value"]),
            metrics["kpis"]["total_reservations"]["label"],
            metrics["kpis"]["total_reservations"]["color"],
            metrics["kpis"]["total_reservations"]["caption"],
        )
        self.kpi_cards["total_revenue"].update_card(
            format_currency(metrics["kpis"]["total_revenue"]["value"]),
            metrics["kpis"]["total_revenue"]["label"],
            metrics["kpis"]["total_revenue"]["color"],
            metrics["kpis"]["total_revenue"]["caption"],
        )
        self.kpi_cards["occupancy_rate"].update_card(
            f"{metrics['kpis']['occupancy_rate']['value']:.1f}%",
            metrics["kpis"]["occupancy_rate"]["label"],
            metrics["kpis"]["occupancy_rate"]["color"],
            metrics["kpis"]["occupancy_rate"]["caption"],
        )
        self.kpi_cards["most_requested_hour"].update_card(
            metrics["kpis"]["most_requested_hour"]["value"],
            metrics["kpis"]["most_requested_hour"]["label"],
            metrics["kpis"]["most_requested_hour"]["color"],
            metrics["kpis"]["most_requested_hour"]["caption"],
        )

        top_hours = ", ".join(f"{hour} ({count})" for hour, count in metrics["top_hours"]) or "Sin datos"
        low_hours = ", ".join(f"{hour} ({count})" for hour, count in metrics["least_hours"]) or "Sin datos"
        schedule_resume = ", ".join(
            f"{label}: {metrics['schedule_distribution'][label]}" for label in SCHEDULE_LABELS
        )

        self.insight_var.set(metrics["headline_insight"])
        self.insights_list_var.set("\n".join(f"- {insight}" for insight in metrics["insights"]))
        self.recommendations_var.set("\n".join(f"- {item}" for item in metrics["recommendations"]))
        self.context_var.set(
            f"Reservas confirmadas: {format_currency(metrics['confirmed_revenue'])}\n"
            f"Reservas pendientes: {format_currency(metrics['pending_revenue'])}\n"
            f"Top horas: {top_hours}\n"
            f"Horas de menor movimiento: {low_hours}\n"
            f"Distribucion por jornada: {schedule_resume}\n\n"
            f"Ninos: {'Si' if settings.allow_children else 'No'}\n"
            f"Mascotas: {'Si' if settings.allow_pets else 'No'}\n"
            f"Recargo fin de semana: {settings.weekend_surcharge:.0f}%\n"
            f"Descuento por grupo ({settings.bulk_people_threshold}+ personas): {settings.bulk_discount:.0f}%\n\n"
            f"Sede: {LOCATION_INFO['direccion']}"
        )
        self._render_chart(metrics["reservations_by_hour"], metrics["most_requested_hour"])

    def _render_chart(self, data: dict[str, int], peak_hour: str) -> None:
        palette = chart_colors()
        self.figure.clear()
        self.figure.patch.set_facecolor(palette["background"])
        axis = self.figure.add_subplot(111)
        axis.set_facecolor(palette["background"])

        hours = list(data.keys())
        values = list(data.values())
        colors = [palette["bar_peak"] if hour == peak_hour else palette["bar"] for hour in hours]
        axis.bar(hours, values, color=colors, width=0.66, edgecolor="none")
        axis.set_title("Reservas por hora", color=palette["text"], fontsize=15, pad=12, fontweight="bold")
        axis.set_xlabel("Hora", color=palette["text"])
        axis.set_ylabel("Cantidad de reservas", color=palette["text"])
        axis.tick_params(axis="x", rotation=45, colors=palette["text"])
        axis.tick_params(axis="y", colors=palette["text"])
        axis.grid(axis="y", linestyle="--", alpha=0.22, color=palette["grid"])
        for spine in axis.spines.values():
            spine.set_color(palette["grid"])
        self.figure.tight_layout()
        self.canvas.draw_idle()
