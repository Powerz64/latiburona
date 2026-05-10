import customtkinter as ctk

from app.ui.theme import COLORS, FONTS, surface_kwargs, tone_palette


class SurfaceCard(ctk.CTkFrame):
    def __init__(self, parent, **kwargs) -> None:
        config = surface_kwargs()
        config.update(kwargs)
        super().__init__(parent, **config)


class KPICard(SurfaceCard):
    def __init__(self, parent, title: str) -> None:
        super().__init__(parent)
        self.grid_columnconfigure(0, weight=1)

        self.accent_bar = ctk.CTkFrame(self, height=6, corner_radius=12, fg_color=COLORS["primary"])
        self.accent_bar.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 10))

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=1, column=0, sticky="ew", padx=18)
        header.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            header,
            text=title,
            font=FONTS["body_bold"],
            text_color=COLORS["text_secondary"],
        )
        self.title_label.grid(row=0, column=0, sticky="w")

        self.badge_label = ctk.CTkLabel(
            header,
            text="Estable",
            width=118,
            height=28,
            corner_radius=14,
            font=FONTS["small"],
            text_color="#0F172A",
            fg_color="#D8F6FF",
        )
        self.badge_label.grid(row=0, column=1, sticky="e")

        self.value_label = ctk.CTkLabel(
            self,
            text="--",
            font=FONTS["kpi"],
            text_color=COLORS["primary"],
        )
        self.value_label.grid(row=2, column=0, sticky="w", padx=18, pady=(8, 0))

        self.caption_label = ctk.CTkLabel(
            self,
            text="",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
            justify="left",
            wraplength=220,
        )
        self.caption_label.grid(row=3, column=0, sticky="ew", padx=18, pady=(8, 16))

    def update_card(self, value: str, status_label: str, tone: str, caption: str) -> None:
        palette = tone_palette(tone)
        self.value_label.configure(text=value, text_color=palette["accent"])
        self.caption_label.configure(text=caption)
        self.badge_label.configure(text=status_label, fg_color=palette["badge"], text_color=palette["text"])
        self.accent_bar.configure(fg_color=palette["accent"])
        self.configure(border_color=palette["accent"])
