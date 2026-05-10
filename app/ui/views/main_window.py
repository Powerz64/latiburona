import customtkinter as ctk

from app.ui.theme import COLORS, FONTS, PRIMARY
from app.ui.views.dashboard_view import DashboardView
from app.ui.views.reports_view import ReportsView
from app.ui.views.reservations_view import ReservationsView
from app.ui.views.settings_view import SettingsView
from app.ui.views.tournaments_view import TournamentsView
from app.utils.constants import APP_NAME


class MainWindow(ctk.CTk):
    def __init__(self, services: dict) -> None:
        super().__init__()
        self.services = services
        self.title(f"{APP_NAME} | Sistema de inteligencia operativa")
        self.geometry("1500x930")
        self.minsize(1340, 820)
        self.configure(fg_color=COLORS["app_bg"])

        self.page_descriptions = {
            "Dashboard": "KPIs, ocupacion, insights y comportamiento operativo de las reservas.",
            "Reservas": "Registro, confirmacion, edicion y control comercial de reservas.",
            "Torneos": "Seguimiento de torneos internos con participantes y estado.",
            "Reportes": "Resumen ejecutivo y exportacion de datos operativos.",
            "Configuracion": "Tarifas, promociones, politicas de ingreso y sede.",
        }
        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        self.views: dict[str, ctk.CTkFrame] = {}

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.header_title_var = ctk.StringVar(value="Dashboard")
        self.header_description_var = ctk.StringVar(value=self.page_descriptions["Dashboard"])

        self._build_sidebar()
        self._build_main_area()
        self._create_views()
        self.show_view("Dashboard")

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(self, width=270, corner_radius=0, fg_color=COLORS["sidebar"])
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(7, weight=1)
        sidebar.grid_propagate(False)

        ctk.CTkLabel(
            sidebar,
            text=APP_NAME,
            font=("Segoe UI", 30, "bold"),
            text_color="#F8FAFC",
        ).grid(row=0, column=0, sticky="w", padx=24, pady=(28, 6))
        ctk.CTkLabel(
            sidebar,
            text="Decision system para\nreservas deportivas en Barranquilla",
            justify="left",
            font=FONTS["body"],
            text_color="#94A3B8",
        ).grid(row=1, column=0, sticky="w", padx=24, pady=(0, 24))

        for row_index, name in enumerate(
            ["Dashboard", "Reservas", "Torneos", "Reportes", "Configuracion"],
            start=2,
        ):
            button = ctk.CTkButton(
                sidebar,
                text=name,
                height=46,
                corner_radius=16,
                anchor="w",
                fg_color="transparent",
                hover_color=COLORS["sidebar_hover"],
                font=FONTS["body_bold"],
                command=lambda page=name: self.show_view(page),
            )
            button.grid(row=row_index, column=0, sticky="ew", padx=18, pady=6)
            self.nav_buttons[name] = button

        ctk.CTkLabel(
            sidebar,
            text="LaTiburona ahora combina operacion,\nanalitica e insights accionables.",
            justify="left",
            wraplength=210,
            font=FONTS["small"],
            text_color="#64748B",
        ).grid(row=8, column=0, sticky="sw", padx=24, pady=(0, 28))

    def _build_main_area(self) -> None:
        main_area = ctk.CTkFrame(self, fg_color="transparent")
        main_area.grid(row=0, column=1, sticky="nsew")
        main_area.grid_rowconfigure(1, weight=1)
        main_area.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(main_area, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 0))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, textvariable=self.header_title_var, font=FONTS["hero"]).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkLabel(
            header,
            textvariable=self.header_description_var,
            font=FONTS["body"],
            text_color=COLORS["text_secondary"],
        ).grid(row=1, column=0, sticky="w", pady=(2, 10))

        self.content_container = ctk.CTkFrame(main_area, fg_color="transparent")
        self.content_container.grid(row=1, column=0, sticky="nsew")
        self.content_container.grid_rowconfigure(0, weight=1)
        self.content_container.grid_columnconfigure(0, weight=1)

    def _create_views(self) -> None:
        self.views = {
            "Dashboard": DashboardView(
                self.content_container,
                self,
                self.services["analytics_service"],
                self.services["settings_service"],
            ),
            "Reservas": ReservationsView(
                self.content_container,
                self,
                self.services["reservation_service"],
            ),
            "Torneos": TournamentsView(
                self.content_container,
                self,
                self.services["tournament_service"],
            ),
            "Reportes": ReportsView(
                self.content_container,
                self,
                self.services["reservation_service"],
                self.services["analytics_service"],
                self.services["export_service"],
            ),
            "Configuracion": SettingsView(
                self.content_container,
                self,
                self.services["settings_service"],
            ),
        }

        for view in self.views.values():
            view.grid(row=0, column=0, sticky="nsew")

    def show_view(self, name: str) -> None:
        self.header_title_var.set(name)
        self.header_description_var.set(self.page_descriptions.get(name, ""))
        for view_name, button in self.nav_buttons.items():
            if view_name == name:
                button.configure(fg_color=PRIMARY, hover_color=PRIMARY, text_color="#082F49")
            else:
                button.configure(fg_color="transparent", hover_color=COLORS["sidebar_hover"], text_color="#F8FAFC")

        selected_view = self.views[name]
        selected_view.tkraise()
        if hasattr(selected_view, "refresh_data"):
            selected_view.refresh_data()

    def refresh_all_views(self) -> None:
        for view in self.views.values():
            if hasattr(view, "refresh_data"):
                view.refresh_data()
