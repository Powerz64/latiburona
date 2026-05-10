from tkinter import messagebox

import customtkinter as ctk

from app.ui.components import SurfaceCard, create_treeview
from app.ui.theme import COLORS, FONTS, button_style
from app.utils.constants import TOURNAMENT_CATEGORIES, TOURNAMENT_STATUS_OPTIONS
from app.utils.formatters import format_date
from app.utils.validators import ValidationError


class TournamentsView(ctk.CTkFrame):
    def __init__(self, parent, controller, tournament_service) -> None:
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.tournament_service = tournament_service
        self.current_tournament_id: int | None = None

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.name_var = ctk.StringVar()
        self.category_var = ctk.StringVar(value=TOURNAMENT_CATEGORIES[0])
        self.status_var = ctk.StringVar(value=TOURNAMENT_STATUS_OPTIONS[0].title())
        self.participant_count_var = ctk.StringVar(value="Participantes detectados: 0")
        self.summary_var = ctk.StringVar(value="")

        self._build_form_panel()
        self._build_table_panel()
        self.refresh_data()

    def _build_form_panel(self) -> None:
        panel = SurfaceCard(self, width=405)
        panel.grid(row=0, column=0, sticky="nsw", padx=(12, 8), pady=12)
        panel.grid_propagate(False)

        ctk.CTkLabel(panel, text="Gestion de torneos", font=FONTS["title"]).pack(anchor="w", padx=18, pady=(18, 10))
        ctk.CTkLabel(panel, text="Nombre del torneo", font=FONTS["body_bold"]).pack(anchor="w", padx=18, pady=(0, 6))
        ctk.CTkEntry(panel, textvariable=self.name_var, height=40).pack(fill="x", padx=18, pady=(0, 12))

        ctk.CTkLabel(panel, text="Categoria", font=FONTS["body_bold"]).pack(anchor="w", padx=18, pady=(0, 6))
        ctk.CTkComboBox(
            panel,
            values=TOURNAMENT_CATEGORIES,
            variable=self.category_var,
            state="readonly",
            height=40,
        ).pack(fill="x", padx=18, pady=(0, 12))

        ctk.CTkLabel(panel, text="Estado", font=FONTS["body_bold"]).pack(anchor="w", padx=18, pady=(0, 6))
        ctk.CTkComboBox(
            panel,
            values=[status.title() for status in TOURNAMENT_STATUS_OPTIONS],
            variable=self.status_var,
            state="readonly",
            height=40,
        ).pack(fill="x", padx=18, pady=(0, 12))

        ctk.CTkLabel(
            panel,
            text="Participantes (uno por linea o separados por coma)",
            font=FONTS["body_bold"],
        ).pack(anchor="w", padx=18, pady=(0, 6))
        self.participants_box = ctk.CTkTextbox(panel, height=210)
        self.participants_box.pack(fill="both", padx=18, pady=(0, 8))
        self.participants_box.bind("<KeyRelease>", lambda _event: self._update_participant_preview())

        ctk.CTkLabel(
            panel,
            textvariable=self.participant_count_var,
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
        ).pack(anchor="w", padx=18, pady=(0, 12))

        buttons = ctk.CTkFrame(panel, fg_color="transparent")
        buttons.pack(fill="x", padx=18, pady=(0, 18))
        buttons.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(
            buttons,
            text="Guardar torneo",
            command=self.save_tournament,
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
        panel.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 8))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Torneos internos", font=FONTS["title"]).grid(row=0, column=0, sticky="w")

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(
            actions,
            text="Editar",
            width=94,
            command=self.load_selected_tournament,
            **button_style("primary"),
        ).grid(
            row=0, column=0, padx=4
        )
        ctk.CTkButton(
            actions,
            text="Eliminar",
            width=94,
            command=self.delete_selected_tournament,
            **button_style("danger"),
        ).grid(row=0, column=1, padx=4)
        ctk.CTkButton(
            actions,
            text="Refrescar",
            width=94,
            command=self.refresh_data,
            **button_style("secondary"),
        ).grid(row=0, column=2, padx=4)

        summary_box = ctk.CTkFrame(panel, fg_color=COLORS["surface_alt"], corner_radius=16)
        summary_box.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))
        ctk.CTkLabel(
            summary_box,
            textvariable=self.summary_var,
            justify="left",
            font=FONTS["body"],
            text_color=COLORS["text_secondary"],
        ).pack(anchor="w", padx=16, pady=14)

        columns = [
            ("id", "ID", 60),
            ("name", "Torneo", 220),
            ("category", "Categoria", 110),
            ("count", "Participantes", 110),
            ("status", "Estado", 110),
            ("created", "Creado", 110),
        ]
        tree_container, self.tree = create_treeview(panel, columns, height=18)
        tree_container.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 18))
        self.tree.bind("<Double-1>", lambda _event: self.load_selected_tournament())

    def _update_participant_preview(self) -> None:
        participants = self.participants_box.get("1.0", "end").strip()
        count = self.tournament_service.get_participant_count(participants)
        self.participant_count_var.set(f"Participantes detectados: {count}")

    def save_tournament(self) -> None:
        payload = {
            "name": self.name_var.get(),
            "category": self.category_var.get(),
            "participants": self.participants_box.get("1.0", "end").strip(),
            "status": self.status_var.get().lower(),
        }
        try:
            if self.current_tournament_id is None:
                self.tournament_service.create_tournament(payload)
                messagebox.showinfo("Torneo creado", "El torneo fue registrado correctamente.")
            else:
                self.tournament_service.update_tournament(self.current_tournament_id, payload)
                messagebox.showinfo("Torneo actualizado", "El torneo fue actualizado correctamente.")
        except ValidationError as exc:
            messagebox.showerror("Validacion", str(exc))
            return

        self.clear_form()
        self.refresh_data()

    def clear_form(self) -> None:
        self.current_tournament_id = None
        self.name_var.set("")
        self.category_var.set(TOURNAMENT_CATEGORIES[0])
        self.status_var.set(TOURNAMENT_STATUS_OPTIONS[0].title())
        self.participants_box.delete("1.0", "end")
        self.participant_count_var.set("Participantes detectados: 0")

    def refresh_data(self) -> None:
        tournaments = self.tournament_service.get_all_tournaments()
        summary = self.tournament_service.get_status_summary()

        self.summary_var.set(
            f"Activos: {summary['activo']}  |  Finalizados: {summary['finalizado']}  |  "
            f"Torneos totales: {len(tournaments)}"
        )

        for item in self.tree.get_children():
            self.tree.delete(item)

        for tournament in tournaments:
            self.tree.insert(
                "",
                "end",
                iid=str(tournament.id),
                values=(
                    tournament.id,
                    tournament.name,
                    tournament.category,
                    tournament.participant_count,
                    tournament.status.title(),
                    format_date((tournament.created_at or "")[:10]),
                ),
            )

    def _selected_id(self) -> int | None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Seleccion requerida", "Selecciona un torneo en la tabla.")
            return None
        return int(selected[0])

    def load_selected_tournament(self) -> None:
        tournament_id = self._selected_id()
        if tournament_id is None:
            return
        tournament = self.tournament_service.get_tournament(tournament_id)
        if tournament is None:
            messagebox.showerror("Torneo", "No se encontro el torneo seleccionado.")
            self.refresh_data()
            return

        self.current_tournament_id = tournament.id
        self.name_var.set(tournament.name)
        self.category_var.set(tournament.category)
        self.status_var.set(tournament.status.title())
        self.participants_box.delete("1.0", "end")
        self.participants_box.insert("1.0", tournament.participants)
        self._update_participant_preview()

    def delete_selected_tournament(self) -> None:
        tournament_id = self._selected_id()
        if tournament_id is None:
            return
        if not messagebox.askyesno("Eliminar torneo", "Esta accion eliminara el torneo seleccionado."):
            return

        self.tournament_service.delete_tournament(tournament_id)
        if self.current_tournament_id == tournament_id:
            self.clear_form()
        messagebox.showinfo("Torneo eliminado", "El torneo fue eliminado correctamente.")
        self.refresh_data()
