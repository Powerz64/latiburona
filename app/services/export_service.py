import csv
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.utils.formatters import format_currency, format_date, format_reservation_window
from app.utils.paths import export_file_path


class ExportService:
    def __init__(self, pricing_service) -> None:
        self.pricing_service = pricing_service

    def _promotion_text(self, reservation) -> str:
        pricing = self.pricing_service.calculate_price(
            reservation.reservation_date,
            reservation.start_time,
            reservation.people_count,
            reservation.end_time,
        )
        return " | ".join(pricing.applied_labels) if pricing.applied_labels else "Sin promociones"

    def _resolve_export_path(self, file_path: str) -> str:
        filename = Path(file_path).name
        return export_file_path(filename)

    def export_reservations_to_csv(self, file_path: str, reservations: list) -> None:
        export_path = self._resolve_export_path(file_path)
        with open(export_path, "w", newline="", encoding="utf-8-sig") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(
                [
                    "ID",
                    "Cliente",
                    "Servicio",
                    "Fecha",
                    "Hora inicio",
                    "Hora fin",
                    "Rango",
                    "Personas",
                    "Telefono",
                    "Direccion",
                    "Jornada",
                    "Subtotal",
                    "Descuento",
                    "Promociones",
                    "Total",
                    "Estado",
                ]
            )
            for item in reservations:
                writer.writerow(
                    [
                        item.id,
                        item.client_name,
                        item.service_type,
                        item.reservation_date,
                        item.start_time,
                        item.end_time,
                        format_reservation_window(item.start_time, item.end_time),
                        item.people_count,
                        item.phone,
                        item.address,
                        item.schedule,
                        item.subtotal,
                        item.discount,
                        self._promotion_text(item),
                        item.total,
                        item.status,
                    ]
                )

    def export_reservations_to_pdf(self, file_path: str, reservations: list, metrics: dict) -> None:
        export_path = self._resolve_export_path(file_path)
        document = SimpleDocTemplate(
            export_path,
            pagesize=landscape(A4),
            rightMargin=24,
            leftMargin=24,
            topMargin=24,
            bottomMargin=24,
        )

        styles = getSampleStyleSheet()
        title_style = styles["Title"]
        title_style.textColor = colors.HexColor("#0F172A")
        normal_style = styles["BodyText"]
        normal_style.leading = 15

        elements = [
            Paragraph("Reporte de Reservas - LaTiburona", title_style),
            Spacer(1, 10),
            Paragraph(
                f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} en Barranquilla, Colombia.",
                normal_style,
            ),
            Spacer(1, 14),
        ]

        summary_data = [
            ["Indicador", "Valor"],
            ["Total de reservas", str(metrics["total_reservations"])],
            ["Ingresos proyectados", format_currency(metrics["total_revenue"])],
            ["Ingresos confirmados", format_currency(metrics["confirmed_revenue"])],
            ["Ingresos hoy", format_currency(metrics.get("revenue_today", 0))],
            ["Ingresos semana", format_currency(metrics.get("revenue_week", 0))],
            ["Confirmadas / pendientes", f"{metrics.get('confirmed_reservations', 0)} / {metrics.get('pending_reservations', 0)}"],
            ["Ocupacion", f"{metrics['occupancy_rate']:.1f}%"],
            ["Cancha lider", metrics.get("top_court", "--")],
            ["Hora mas solicitada", metrics["most_requested_hour"]],
            ["Hora menos solicitada", metrics["least_requested_hour"]],
            ["Franjas lideres", ", ".join(f"{label} ({count})" for label, count in metrics["peak_ranges"]) or "Sin datos"],
        ]

        summary_table = Table(summary_data, colWidths=[200, 220])
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D4ED8")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
                ]
            )
        )
        elements.extend([summary_table, Spacer(1, 18)])
        elements.append(Paragraph("Insights automaticos", styles["Heading2"]))
        insight_text = "<br/>".join(f"- {item}" for item in metrics["insights"]) or "- Sin insights disponibles."
        elements.extend([Paragraph(insight_text, normal_style), Spacer(1, 14)])

        reservations_data = [
            ["Cliente", "Servicio", "Fecha", "Rango", "Personas", "Promociones", "Estado", "Total"]
        ]
        for item in reservations:
            reservations_data.append(
                [
                    item.client_name,
                    item.service_type,
                    format_date(item.reservation_date),
                    format_reservation_window(item.start_time, item.end_time),
                    str(item.people_count),
                    self._promotion_text(item),
                    item.status.title(),
                    format_currency(item.total),
                ]
            )

        reservations_table = Table(
            reservations_data,
            repeatRows=1,
            colWidths=[120, 95, 75, 90, 55, 190, 75, 95],
        )
        reservations_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F766E")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#FFFFFF")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                ]
            )
        )
        elements.append(reservations_table)
        document.build(elements)
