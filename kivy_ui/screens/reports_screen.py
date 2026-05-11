from __future__ import annotations

from datetime import datetime

from kivy.app import App
from kivy.metrics import dp
from kivy.properties import StringProperty

from app.utils.formatters import format_currency, format_reservation_window
from app.utils.paths import EXPORTS_DIR, ensure_exports_dir, export_file_path
from kivy_ui.screens.base_screen import ServiceScreen


class ReportsScreen(ServiceScreen):
    summary_text = StringProperty("")
    report_text = StringProperty("")
    insights_text = StringProperty("")
    recommendations_text = StringProperty("")
    export_status = StringProperty("Sin exportaciones recientes.")
    export_path_text = StringProperty(EXPORTS_DIR)

    def on_kv_post(self, *_args) -> None:
        self.bind(size=self._update_layout)
        self._update_layout()

    def _can_access_reports(self) -> bool:
        role = str((App.get_running_app().current_user or {}).get("role", "")).strip().lower()
        return role in {"admin", "operator"}

    def _update_layout(self, *_args) -> None:
        if not self.ids:
            return
        self.ids.export_grid.cols = 1 if self.width < dp(980) else 3
        self.ids.bottom_grid.cols = 1 if self.width < dp(1020) else 3

    def refresh(self) -> None:
        if not self._can_access_reports():
            self.summary_text = ""
            self.report_text = "Acceso restringido."
            self.insights_text = ""
            self.recommendations_text = ""
            self.notify("Acceso restringido", "Acceso restringido", tone="warning")
            self.set_status("Acceso restringido")
            return
        self.set_status("Cargando reportes...")
        self.load_data(
            "reports_refresh",
            self._fetch_reports_data,
            self._apply_reports_data,
            self._handle_reports_error,
            loading_message="Preparando reportes ejecutivos...",
            show_loading_overlay=False,
        )

    def _fetch_reports_data(self) -> dict:
        metrics = self.get_service("analytics_service").get_dashboard_metrics()
        reservations = self.get_service("reservation_service").get_all_reservations()

        summary_text = (
            f"Total partidos: {metrics['total_reservations']}\n"
            f"Ingresos proyectados: {format_currency(metrics['total_revenue'])}\n"
            f"Ingresos confirmados: {format_currency(metrics['confirmed_revenue'])}\n"
            f"Ocupacion: {metrics['occupancy_rate']:.1f}%\n"
            f"Hora pico: {metrics['most_requested_hour']}\n"
            f"Hora baja: {metrics['least_requested_hour']}\n"
            f"Franjas lideres: {', '.join(f'{label} ({count})' for label, count in metrics['peak_ranges']) or 'Sin datos'}"
        )

        report_lines = [
            f"Corte operativo: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            "",
            "Detalle de partidos:",
        ]
        if not reservations:
            report_lines.append("- No hay reservas registradas todavia.")
        else:
            for reservation in reservations:
                report_lines.append(
                    f"- {reservation.client_name} | {reservation.service_type} | "
                    f"{reservation.reservation_date} {format_reservation_window(reservation.start_time, reservation.end_time)} | "
                    f"{reservation.status.title()} | {format_currency(reservation.total)}"
                )

        return {
            "metrics": metrics,
            "summary_text": summary_text,
            "report_text": "\n".join(report_lines),
            "insights_text": "\n".join(f"- {item}" for item in metrics["insights"]) or "- Sin insights disponibles.",
            "recommendations_text": (
                "\n".join(f"- {item}" for item in metrics["recommendations"])
                or "- Sin recomendaciones disponibles."
            ),
        }

    def _apply_reports_data(self, payload: dict) -> None:
        metrics = dict(payload.get("metrics") or {})
        self.summary_text = payload["summary_text"]
        self.report_text = payload["report_text"]
        self.insights_text = payload["insights_text"]
        self.recommendations_text = payload["recommendations_text"]
        self.ids.report_revenue_card.set_data(
            {
                "title": "Ingresos totales",
                "value": format_currency(metrics.get("total_revenue", 0)),
                "status": "Revenue",
                "tone": "success" if metrics.get("total_revenue", 0) else "primary",
                "caption": "Reservas y partidos proyectados.",
            }
        )
        self.ids.report_confirmed_card.set_data(
            {
                "title": "Confirmado",
                "value": format_currency(metrics.get("confirmed_revenue", 0)),
                "status": "Caja segura",
                "tone": "primary",
                "caption": "Ingreso ya confirmado por el club.",
            }
        )
        self.ids.report_occupancy_card.set_data(
            {
                "title": "Ocupacion",
                "value": f"{float(metrics.get('occupancy_rate', 0) or 0):.1f}%",
                "status": "En vivo",
                "tone": "success" if float(metrics.get("occupancy_rate", 0) or 0) >= 70 else "warning",
                "caption": "Uso operativo de franjas disponibles.",
            }
        )
        self.ids.report_peak_card.set_data(
            {
                "title": "Hora prime",
                "value": str(metrics.get("most_requested_hour") or "--"),
                "status": "Demanda",
                "tone": "primary",
                "caption": "Franja con mayor ritmo deportivo.",
            }
        )
        if "reports_hour_chart" in self.ids:
            self.ids.reports_hour_chart.set_data(
                dict(metrics.get("reservations_by_hour") or {}),
                str(metrics.get("most_requested_hour") or ""),
            )
        self.ids.reports_insights_card.apply_data(
            "Lectura de cancha",
            self.insights_text,
            eyebrow="Lectura operativa",
            badge="Analitica",
            icon="⚽",
            tone="primary",
        )
        self.ids.reports_recommendations_card.apply_data(
            "Jugadas sugeridas",
            self.recommendations_text,
            eyebrow="Plan de ocupacion",
            badge="Prioridad",
            icon="🏆",
            tone="success",
            highlighted=True,
        )
        self.set_status("Reportes deportivos listos para analisis y exportacion.")

    def _handle_reports_error(self, error: Exception) -> None:
        self.summary_text = "No fue posible cargar los reportes."
        self.report_text = "Intenta nuevamente en unos segundos."
        self.insights_text = "- Sin datos disponibles."
        self.recommendations_text = "- Sin recomendaciones disponibles."
        for card_id in ("report_revenue_card", "report_confirmed_card", "report_occupancy_card", "report_peak_card"):
            if card_id in self.ids:
                self.ids[card_id].set_error("Sin datos")
        self.ids.reports_insights_card.set_error("No fue posible cargar insights.")
        self.ids.reports_recommendations_card.set_error("No fue posible cargar recomendaciones.")
        self.set_status(f"Error al cargar reportes: {error}")

    def export_csv(self) -> None:
        self.set_status("Generando archivo CSV...")
        self.run_in_background(
            "reports_export_csv",
            self._perform_export_csv,
            self._handle_export_success,
            self._handle_export_error,
        )

    def export_pdf(self) -> None:
        self.set_status("Generando reporte PDF...")
        self.run_in_background(
            "reports_export_pdf",
            self._perform_export_pdf,
            self._handle_export_success,
            self._handle_export_error,
        )

    def _perform_export_csv(self) -> dict:
        reservations = self.get_service("reservation_service").get_all_reservations()
        ensure_exports_dir()
        filename = f"reservas_latiburona_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        export_path = export_file_path(filename)
        self.get_service("export_service").export_reservations_to_csv(filename, reservations)
        return {"path": export_path}

    def _perform_export_pdf(self) -> dict:
        reservations = self.get_service("reservation_service").get_all_reservations()
        metrics = self.get_service("analytics_service").get_dashboard_metrics()
        ensure_exports_dir()
        filename = f"reporte_latiburona_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        export_path = export_file_path(filename)
        self.get_service("export_service").export_reservations_to_pdf(filename, reservations, metrics)
        return {"path": export_path}

    def _handle_export_success(self, payload: dict) -> None:
        self.export_status = f"Exportacion completada: {payload['path']}"
        self.notify("Exportacion completada", self.export_status, tone="success")
        self.set_status(self.export_status)

    def _handle_export_error(self, error: Exception) -> None:
        self.notify("Exportacion", "No fue posible completar la exportacion.", tone="danger")
        self.set_status(f"Error al exportar: {error}")
