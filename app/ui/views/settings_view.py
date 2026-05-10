from tkinter import messagebox

import customtkinter as ctk

from app.ui.components import SurfaceCard
from app.ui.theme import COLORS, FONTS, button_style
from app.utils.constants import DEFAULT_SETTINGS, LOCATION_INFO
from app.utils.formatters import format_currency
from app.utils.validators import ValidationError


class SettingsView(ctk.CTkFrame):
    def __init__(self, parent, controller, settings_service) -> None:
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.settings_service = settings_service

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.price_morning_var = ctk.StringVar()
        self.price_afternoon_var = ctk.StringVar()
        self.price_night_var = ctk.StringVar()
        self.weekend_surcharge_var = ctk.StringVar()
        self.bulk_threshold_var = ctk.StringVar()
        self.bulk_discount_var = ctk.StringVar()
        self.allow_children_var = ctk.BooleanVar(value=True)
        self.allow_pets_var = ctk.BooleanVar(value=False)
        self.appearance_var = ctk.StringVar(value=ctk.get_appearance_mode())

        self._build_form_panel()
        self._build_preview_panel()
        self.refresh_data()

    def _build_form_panel(self) -> None:
        panel = SurfaceCard(self)
        panel.grid(row=0, column=0, sticky="nsew", padx=(12, 8), pady=12)

        ctk.CTkLabel(panel, text="Configuracion del negocio", font=FONTS["title"]).pack(
            anchor="w", padx=18, pady=(18, 12)
        )

        self._add_entry(panel, "Tarifa manana", self.price_morning_var)
        self._add_entry(panel, "Tarifa tarde", self.price_afternoon_var)
        self._add_entry(panel, "Tarifa noche", self.price_night_var)
        self._add_entry(panel, "Recargo fin de semana (%)", self.weekend_surcharge_var)
        self._add_entry(panel, "Grupo grande desde", self.bulk_threshold_var)
        self._add_entry(panel, "Descuento por grupo (%)", self.bulk_discount_var)

        ctk.CTkSwitch(panel, text="Se aceptan ninos", variable=self.allow_children_var).pack(
            anchor="w", padx=18, pady=(6, 10)
        )
        ctk.CTkSwitch(panel, text="Se aceptan mascotas", variable=self.allow_pets_var).pack(
            anchor="w", padx=18, pady=(0, 12)
        )

        ctk.CTkLabel(panel, text="Modo visual", font=FONTS["body_bold"]).pack(anchor="w", padx=18, pady=(0, 6))
        ctk.CTkOptionMenu(
            panel,
            values=["Dark", "Light", "System"],
            variable=self.appearance_var,
            command=self.change_appearance_mode,
            height=40,
        ).pack(fill="x", padx=18, pady=(0, 16))

        buttons = ctk.CTkFrame(panel, fg_color="transparent")
        buttons.pack(fill="x", padx=18, pady=(0, 18))
        buttons.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(
            buttons,
            text="Guardar cambios",
            command=self.save_settings,
            height=42,
            **button_style("primary"),
        ).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ctk.CTkButton(
            buttons,
            text="Restaurar",
            command=self.restore_defaults,
            height=42,
            **button_style("secondary"),
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def _build_preview_panel(self) -> None:
        panel = SurfaceCard(self)
        panel.grid(row=0, column=1, sticky="nsew", padx=(8, 12), pady=12)
        panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(panel, text="Vista operativa", font=FONTS["title"]).grid(
            row=0, column=0, sticky="w", padx=18, pady=(18, 12)
        )

        location_text = (
            f"Direccion: {LOCATION_INFO['direccion']}\n\n"
            f"Como llegar: {LOCATION_INFO['como_llegar']}\n\n"
            f"Puntos de referencia: {LOCATION_INFO['puntos_referencia']}"
        )
        ctk.CTkLabel(
            panel,
            text=location_text,
            justify="left",
            wraplength=430,
            font=FONTS["body"],
            text_color=COLORS["text_secondary"],
        ).grid(row=1, column=0, sticky="nw", padx=18, pady=(0, 18))

        self.preview_box = ctk.CTkTextbox(panel, height=320)
        self.preview_box.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 18))

    def _add_entry(self, parent, label: str, variable: ctk.StringVar) -> None:
        ctk.CTkLabel(parent, text=label, font=FONTS["body_bold"]).pack(anchor="w", padx=18, pady=(0, 6))
        ctk.CTkEntry(parent, textvariable=variable, height=40).pack(fill="x", padx=18, pady=(0, 12))

    def refresh_data(self) -> None:
        settings = self.settings_service.load_settings()
        self.price_morning_var.set(f"{settings.price_morning:.0f}")
        self.price_afternoon_var.set(f"{settings.price_afternoon:.0f}")
        self.price_night_var.set(f"{settings.price_night:.0f}")
        self.weekend_surcharge_var.set(f"{settings.weekend_surcharge:.0f}")
        self.bulk_threshold_var.set(str(settings.bulk_people_threshold))
        self.bulk_discount_var.set(f"{settings.bulk_discount:.0f}")
        self.allow_children_var.set(settings.allow_children)
        self.allow_pets_var.set(settings.allow_pets)

        preview_text = (
            "Tarifas configuradas\n"
            f"- Manana: {format_currency(settings.price_morning)}\n"
            f"- Tarde: {format_currency(settings.price_afternoon)}\n"
            f"- Noche: {format_currency(settings.price_night)}\n\n"
            "Reglas comerciales\n"
            f"- Recargo fin de semana: {settings.weekend_surcharge:.0f}%\n"
            f"- Descuento por grupo ({settings.bulk_people_threshold}+): {settings.bulk_discount:.0f}%\n\n"
            "Politicas de ingreso\n"
            f"- Ninos: {'Si' if settings.allow_children else 'No'}\n"
            f"- Mascotas: {'Si' if settings.allow_pets else 'No'}"
        )
        self.preview_box.delete("1.0", "end")
        self.preview_box.insert("1.0", preview_text)

    def save_settings(self) -> None:
        payload = {
            "price_morning": self.price_morning_var.get(),
            "price_afternoon": self.price_afternoon_var.get(),
            "price_night": self.price_night_var.get(),
            "weekend_surcharge": self.weekend_surcharge_var.get(),
            "bulk_people_threshold": self.bulk_threshold_var.get(),
            "bulk_discount": self.bulk_discount_var.get(),
            "allow_children": self.allow_children_var.get(),
            "allow_pets": self.allow_pets_var.get(),
        }
        try:
            self.settings_service.save_settings(payload)
        except ValidationError as exc:
            messagebox.showerror("Validacion", str(exc))
            return

        messagebox.showinfo("Configuracion guardada", "Los cambios se guardaron correctamente.")
        self.controller.refresh_all_views()

    def restore_defaults(self) -> None:
        self.price_morning_var.set(str(int(DEFAULT_SETTINGS["price_morning"])))
        self.price_afternoon_var.set(str(int(DEFAULT_SETTINGS["price_afternoon"])))
        self.price_night_var.set(str(int(DEFAULT_SETTINGS["price_night"])))
        self.weekend_surcharge_var.set(str(int(DEFAULT_SETTINGS["weekend_surcharge"])))
        self.bulk_threshold_var.set(str(DEFAULT_SETTINGS["bulk_people_threshold"]))
        self.bulk_discount_var.set(str(int(DEFAULT_SETTINGS["bulk_discount"])))
        self.allow_children_var.set(bool(DEFAULT_SETTINGS["allow_children"]))
        self.allow_pets_var.set(bool(DEFAULT_SETTINGS["allow_pets"]))
        self.preview_box.delete("1.0", "end")
        self.preview_box.insert("1.0", "Valores por defecto cargados. Presiona Guardar cambios para aplicarlos.")

    def change_appearance_mode(self, mode: str) -> None:
        ctk.set_appearance_mode(mode)
        self.controller.refresh_all_views()
