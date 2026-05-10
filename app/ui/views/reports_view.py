from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk

from app.ui.components import KPICard, SurfaceCard
from app.ui.theme import FONTS, button_style
from app.utils.formatters import format_currency
from app.utils.paths import EXPORTS_DIR, export_file_path, ensure_exports_dir


class ReportsView(ctk.CTkFrame):
    def __init__(self, parent, controller, reservation_service, analytics_service, export_service) -> None:
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.reservation_service = reservation_service
        self.analytics_service = analytics_service
        self.export_service = export_service

        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.kpi_cards: dict[str, KPICard] = {}
        self._build_kpis()
        self._build_report_box()
        self._build_insights_box()

    def _build_kpis(self) -> None:
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 8))
        for index in range(4):
            container.grid_columnconfigure(index, weight=1)

        for index, (key, title) in enumerate(
            [
                ("total_reservations", "Total reservas"),
                ("confirmed_revenue", "Ingresos confirmados"),
                ("occupancy_rate", "Ocupacion"),
                ("least_requested_hour", "Hora baja"),
            ]
        ):
            card = KPICard(container, title)
            card.grid(row=0, column=index, sticky="nsew", padx=8)
            self.kpi_cards[key] = card

    def _build_report_box(self) -> None:
        panel = SurfaceCard(self)
        panel.grid(row=1, column=0, sticky="nsew", padx=(12, 8), pady=(8, 12))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(panel, text="Reporte ejecutivo", font=FONTS["title"]).grid(
            row=0, column=0, sticky="w", padx=18, pady=(18, 10)
        )

        self.report_box = ctk.CTkTextbox(panel)
        self.report_box.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))

    def _build_insights_box(self) -> None:
        panel = SurfaceCard(self)
        panel.grid(row=1, column=1, sticky="nsew", padx=(8, 12), pady=(8, 12))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(panel, text="Acciones y hallazgos", font=FONTS["title"]).grid(
            row=0, column=0, sticky="w", padx=18, pady=(18, 10)
        )

        buttons = ctk.CTkFrame(panel, fg_color="transparent")
        buttons.grid(row=1, column=0, sticky="w", padx=18, pady=(0, 10))
        ctk.CTkButton(buttons, text="Exportar CSV", width=140, command=self.export_csv, **button_style("primary")).grid(
            row=0, column=0, padx=(0, 8)
        )
        ctk.CTkButton(buttons, text="Exportar PDF", width=140, command=self.export_pdf, **button_style("success")).grid(
            row=0, column=1, padx=(8, 0)
        )

        self.insights_box = ctk.CTkTextbox(panel)
        self.insights_box.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 18))

    def refresh_data(self) -> None:
        metrics = self.analytics_service.get_dashboard_metrics()
        reservations = self.reservation_service.get_all_reservations()

        self.kpi_cards["total_reservations"].update_card(
            str(metrics["total_reservations"]),
            metrics["kpis"]["total_reservations"]["label"],
            metrics["kpis"]["total_reservations"]["color"],
            "Registros disponibles para analisis",
        )
        self.kpi_cards["confirmed_revenue"].update_card(
            format_currency(metrics["confirmed_revenue"]),
            "Ingresos fuertes" if metrics["confirmed_revenue"] >= 300000 else "Ingresos bajos",
            "success" if metrics["confirmed_revenue"] >= 300000 else "danger",
            "Facturacion cerrada del periodo",
        )
        self.kpi_cards["occupancy_rate"].update_card(
            f"{metrics['occupancy_rate']:.1f}%",
            metrics["kpis"]["occupancy_rate"]["label"],
            metrics["kpis"]["occupancy_rate"]["color"],
            "Capacidad utilizada por jornadas",
        )
        self.kpi_cards["least_requested_hour"].update_card(
            metrics["least_requested_hour"],
            "Horario por activar" if metrics["least_requested_hour"] != "Sin datos" else "Sin datos",
            "warning" if metrics["least_requested_hour"] != "Sin datos" else "danger",
            "Horario con menor dinamica",
        )

        report_lines = [
            "Resumen ejecutivo de LaTiburona",
            "",
            f"Fecha de corte: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            f"Total de reservas: {metrics['total_reservations']}",
            f"Ingresos proyectados: {format_currency(metrics['total_revenue'])}",
            f"Ingresos confirmados: {format_currency(metrics['confirmed_revenue'])}",
            f"Ocupacion: {metrics['occupancy_rate']:.1f}%",
            f"Hora mas solicitada: {metrics['most_requested_hour']}",
            f"Hora menos solicitada: {metrics['least_requested_hour']}",
            "",
            "Detalle operativo:",
        ]

        if not reservations:
            report_lines.append("No hay reservas registradas.")
        else:
            for reservation in reservations:
                report_lines.append(
                    f"- {reservation.client_name} | {reservation.service_type} | "
                    f"{reservation.reservation_date} {reservation.reservation_time} | "
                    f"{reservation.status.title()} | {format_currency(reservation.total)}"
                )

        self.report_box.delete("1.0", "end")
        self.report_box.insert("1.0", "\n".join(report_lines))

        insight_lines = ["Insights automaticos", ""]
        for insight in metrics["insights"]:
            insight_lines.append(f"- {insight}")
        insight_lines.extend(["", "Recomendaciones inmediatas"])
        for item in metrics["recommendations"]:
            insight_lines.append(f"- {item}")

        self.insights_box.delete("1.0", "end")
        self.insights_box.insert("1.0", "\n".join(insight_lines))

    def export_csv(self) -> None:
        reservations = self.reservation_service.get_all_reservations()
        default_name = f"reservas_latiburona_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        ensure_exports_dir()
        file_path = filedialog.asksaveasfilename(
            title="Guardar CSV",
            defaultextension=".csv",
            initialdir=EXPORTS_DIR,
            initialfile=default_name,
            filetypes=[("Archivo CSV", "*.csv")],
        )
        if not file_path:
            return
        final_path = export_file_path(file_path)
        self.export_service.export_reservations_to_csv(final_path, reservations)
        messagebox.showinfo("Exportacion completada", f"El archivo CSV fue generado en:\n{final_path}")

    def export_pdf(self) -> None:
        reservations = self.reservation_service.get_all_reservations()
        metrics = self.analytics_service.get_dashboard_metrics()
        default_name = f"reporte_latiburona_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        ensure_exports_dir()
        file_path = filedialog.asksaveasfilename(
            title="Guardar PDF",
            defaultextension=".pdf",
            initialdir=EXPORTS_DIR,
            initialfile=default_name,
            filetypes=[("Archivo PDF", "*.pdf")],
        )
        if not file_path:
            return
        final_path = export_file_path(file_path)
        self.export_service.export_reservations_to_pdf(final_path, reservations, metrics)
        messagebox.showinfo("Exportacion completada", f"El reporte PDF fue generado en:\n{final_path}")
