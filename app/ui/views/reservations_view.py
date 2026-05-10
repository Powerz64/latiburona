from tkinter import messagebox

import customtkinter as ctk

from app.ui.components import SurfaceCard, create_treeview
from app.ui.theme import COLORS, FONTS, button_style
from app.utils.constants import SERVICE_TYPES, TIME_OPTIONS
from app.utils.formatters import format_currency, format_date
from app.utils.validators import ValidationError


class ReservationsView(ctk.CTkFrame):
    def __init__(self, parent, controller, reservation_service) -> None:
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.reservation_service = reservation_service
        self.current_reservation_id: int | None = None
        self.current_status = "pendiente"

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.client_name_var = ctk.StringVar()
        self.service_type_var = ctk.StringVar(value=SERVICE_TYPES[0])
        self.date_var = ctk.StringVar()
        self.time_var = ctk.StringVar(value=TIME_OPTIONS[0])
        self.people_var = ctk.StringVar()
        self.phone_var = ctk.StringVar()
        self.address_var = ctk.StringVar()
        self.quote_var = ctk.StringVar(value="Completa fecha, hora y personas para obtener la cotizacion.")

        self._build_form_panel()
        self._build_table_panel()
        self._bind_events()
        self.refresh_data()

    def _build_form_panel(self) -> None:
        panel = SurfaceCard(self, width=395)
        panel.grid(row=0, column=0, sticky="nsw", padx=(12, 8), pady=12)
        panel.grid_propagate(False)

        ctk.CTkLabel(panel, text="Registro de reservas", font=FONTS["title"]).pack(anchor="w", padx=18, pady=(18, 10))

        self._add_entry(panel, "Nombre del cliente", self.client_name_var)
        self._add_combo(panel, "Tipo de servicio/cancha", self.service_type_var, SERVICE_TYPES)
        self._add_entry(panel, "Fecha (AAAA-MM-DD)", self.date_var)
        self._add_combo(panel, "Hora", self.time_var, TIME_OPTIONS)
        self._add_entry(panel, "Cantidad de personas", self.people_var)
        self._add_entry(panel, "Telefono", self.phone_var)
        self._add_entry(panel, "Direccion", self.address_var)

        quote_box = ctk.CTkFrame(panel, fg_color=COLORS["surface_alt"], corner_radius=16)
        quote_box.pack(fill="x", padx=18, pady=(6, 14))
        ctk.CTkLabel(quote_box, text="Cotizacion inteligente", font=FONTS["subtitle"]).pack(
            anchor="w", padx=16, pady=(14, 4)
        )
        ctk.CTkLabel(
            quote_box,
            textvariable=self.quote_var,
            justify="left",
            wraplength=320,
            font=FONTS["body"],
            text_color=COLORS["text_secondary"],
        ).pack(anchor="w", padx=16, pady=(0, 14))

        buttons = ctk.CTkFrame(panel, fg_color="transparent")
        buttons.pack(fill="x", padx=18, pady=(0, 18))
        buttons.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            buttons,
            text="Guardar reserva",
            command=self.save_reservation,
            height=42,
            **button_style("primary"),
        ).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ctk.CTkButton(
            buttons,
            text="Limpiar",
            command=self.clear_form,
            height=42,
            **button_style("secondary"),
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def _build_table_panel(self) -> None:
        panel = SurfaceCard(self)
        panel.grid(row=0, column=1, sticky="nsew", padx=(8, 12), pady=12)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="Reservas registradas", font=FONTS["title"]).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            text="Doble clic para editar. Usa confirmar para cerrar reservas operativas.",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=1, rowspan=2, sticky="e")
        for index in range(4):
            actions.grid_columnconfigure(index, weight=1)

        ctk.CTkButton(
            actions,
            text="Editar",
            width=94,
            command=self.load_selected_reservation,
            **button_style("primary"),
        ).grid(
            row=0, column=0, padx=4
        )
        ctk.CTkButton(
            actions,
            text="Confirmar",
            width=94,
            command=self.confirm_selected_reservation,
            **button_style("success"),
        ).grid(row=0, column=1, padx=4)
        ctk.CTkButton(
            actions,
            text="Eliminar",
            width=94,
            command=self.delete_selected_reservation,
            **button_style("danger"),
        ).grid(row=0, column=2, padx=4)
        ctk.CTkButton(
            actions,
            text="Refrescar",
            width=94,
            command=self.refresh_data,
            **button_style("secondary"),
        ).grid(row=0, column=3, padx=4)

        columns = [
            ("id", "ID", 54),
            ("client", "Cliente", 170),
            ("service", "Servicio", 140),
            ("date", "Fecha", 100),
            ("time", "Hora", 74),
            ("schedule", "Jornada", 88),
            ("people", "Personas", 86),
            ("status", "Estado", 106),
            ("total", "Total", 118),
        ]
        tree_container, self.tree = create_treeview(panel, columns, height=18)
        tree_container.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        self.tree.bind("<Double-1>", lambda _event: self.load_selected_reservation())

    def _add_entry(self, parent, label: str, variable: ctk.StringVar) -> None:
        ctk.CTkLabel(parent, text=label, font=FONTS["body_bold"]).pack(anchor="w", padx=18, pady=(0, 6))
        ctk.CTkEntry(parent, textvariable=variable, height=40).pack(fill="x", padx=18, pady=(0, 12))

    def _add_combo(self, parent, label: str, variable: ctk.StringVar, values: list[str]) -> None:
        ctk.CTkLabel(parent, text=label, font=FONTS["body_bold"]).pack(anchor="w", padx=18, pady=(0, 6))
        ctk.CTkComboBox(parent, values=values, variable=variable, state="readonly", height=40).pack(
            fill="x", padx=18, pady=(0, 12)
        )

    def _bind_events(self) -> None:
        for variable in (self.date_var, self.time_var, self.people_var):
            variable.trace_add("write", self._update_quote)

    def _update_quote(self, *_args) -> None:
        reservation_date = self.date_var.get().strip()
        reservation_time = self.time_var.get().strip()
        people_count = self.people_var.get().strip()

        if not reservation_date or not reservation_time or not people_count:
            self.quote_var.set("Completa fecha, hora y personas para obtener la cotizacion.")
            return

        try:
            pricing = self.reservation_service.get_pricing_preview(
                reservation_date,
                reservation_time,
                people_count,
            )
        except (ValidationError, ValueError):
            self.quote_var.set("Usa una fecha valida y una cantidad de personas numerica.")
            return

        promotions = " | ".join(pricing["applied_labels"]) if pricing["applied_labels"] else "Sin promociones"
        discount_text = (
            f"Descuento aplicado: {pricing['bulk_discount_percent']:.0f}%"
            if pricing["bulk_discount_percent"]
            else "Sin descuento promocional"
        )
        self.quote_var.set(
            f"Jornada: {pricing['schedule']}\n"
            f"Tarifa base: {format_currency(pricing['base_price'])}\n"
            f"Subtotal operativo: {format_currency(pricing['subtotal'])}\n"
            f"{discount_text}\n"
            f"Total final: {format_currency(pricing['total'])}\n"
            f"Promociones: {promotions}"
        )

    def save_reservation(self) -> None:
        payload = {
            "client_name": self.client_name_var.get(),
            "service_type": self.service_type_var.get(),
            "reservation_date": self.date_var.get(),
            "reservation_time": self.time_var.get(),
            "people_count": self.people_var.get(),
            "phone": self.phone_var.get(),
            "address": self.address_var.get(),
            "status": self.current_status,
        }

        try:
            if self.current_reservation_id is None:
                self.reservation_service.create_reservation(payload)
                messagebox.showinfo("Reserva creada", "La reserva fue guardada correctamente.")
            else:
                self.reservation_service.update_reservation(self.current_reservation_id, payload)
                messagebox.showinfo("Reserva actualizada", "La reserva fue actualizada correctamente.")
        except ValidationError as exc:
            messagebox.showerror("Validacion", str(exc))
            return

        self.clear_form()
        self.controller.refresh_all_views()

    def clear_form(self) -> None:
        self.current_reservation_id = None
        self.current_status = "pendiente"
        self.client_name_var.set("")
        self.service_type_var.set(SERVICE_TYPES[0])
        self.date_var.set("")
        self.time_var.set(TIME_OPTIONS[0])
        self.people_var.set("")
        self.phone_var.set("")
        self.address_var.set("")
        self.quote_var.set("Completa fecha, hora y personas para obtener la cotizacion.")

    def refresh_data(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        for reservation in self.reservation_service.get_all_reservations():
            self.tree.insert(
                "",
                "end",
                iid=str(reservation.id),
                values=(
                    reservation.id,
                    reservation.client_name,
                    reservation.service_type,
                    format_date(reservation.reservation_date),
                    reservation.reservation_time,
                    reservation.schedule,
                    reservation.people_count,
                    reservation.status.title(),
                    format_currency(reservation.total),
                ),
            )

    def _selected_id(self) -> int | None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Seleccion requerida", "Selecciona una reserva en la tabla.")
            return None
        return int(selected[0])

    def load_selected_reservation(self) -> None:
        reservation_id = self._selected_id()
        if reservation_id is None:
            return

        reservation = self.reservation_service.get_reservation(reservation_id)
        if reservation is None:
            messagebox.showerror("Reserva", "No se encontro la reserva seleccionada.")
            self.refresh_data()
            return

        self.current_reservation_id = reservation.id
        self.current_status = reservation.status
        self.client_name_var.set(reservation.client_name)
        self.service_type_var.set(reservation.service_type)
        self.date_var.set(reservation.reservation_date)
        self.time_var.set(reservation.reservation_time)
        self.people_var.set(str(reservation.people_count))
        self.phone_var.set(reservation.phone)
        self.address_var.set(reservation.address)
        self._update_quote()

    def confirm_selected_reservation(self) -> None:
        reservation_id = self._selected_id()
        if reservation_id is None:
            return
        self.reservation_service.confirm_reservation(reservation_id)
        if self.current_reservation_id == reservation_id:
            self.current_status = "confirmada"
        messagebox.showinfo("Reserva confirmada", "La reserva fue marcada como confirmada.")
        self.controller.refresh_all_views()

    def delete_selected_reservation(self) -> None:
        reservation_id = self._selected_id()
        if reservation_id is None:
            return
        if not messagebox.askyesno("Eliminar reserva", "Esta accion eliminara la reserva seleccionada."):
            return

        self.reservation_service.delete_reservation(reservation_id)
        if self.current_reservation_id == reservation_id:
            self.clear_form()
        messagebox.showinfo("Reserva eliminada", "La reserva fue eliminada correctamente.")
        self.controller.refresh_all_views()
