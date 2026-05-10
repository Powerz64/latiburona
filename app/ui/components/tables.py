from tkinter import ttk

import customtkinter as ctk

from app.ui.theme import COLORS


def create_treeview(parent, columns: list[tuple[str, str, int]], height: int = 16):
    style = ttk.Style(parent)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure(
        "LaTiburona.Treeview",
        background="#0F172A",
        fieldbackground="#0F172A",
        foreground="#E2E8F0",
        rowheight=32,
        borderwidth=0,
        relief="flat",
        font=("Segoe UI", 10),
    )
    style.map(
        "LaTiburona.Treeview",
        background=[("selected", COLORS["sidebar_active"])],
        foreground=[("selected", "#FFFFFF")],
    )
    style.configure(
        "LaTiburona.Treeview.Heading",
        background="#0E2A40",
        foreground="#F8FAFC",
        relief="flat",
        font=("Segoe UI", 10, "bold"),
        padding=9,
    )
    style.map("LaTiburona.Treeview.Heading", background=[("active", "#1E293B")])

    container = ctk.CTkFrame(parent, fg_color="transparent")
    container.grid_rowconfigure(0, weight=1)
    container.grid_columnconfigure(0, weight=1)

    tree = ttk.Treeview(
        container,
        columns=[column[0] for column in columns],
        show="headings",
        style="LaTiburona.Treeview",
        height=height,
    )

    for column_key, heading, width in columns:
        tree.heading(column_key, text=heading)
        tree.column(column_key, width=width, anchor="center", stretch=True)

    vertical_scroll = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
    horizontal_scroll = ttk.Scrollbar(container, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vertical_scroll.set, xscrollcommand=horizontal_scroll.set)

    tree.grid(row=0, column=0, sticky="nsew")
    vertical_scroll.grid(row=0, column=1, sticky="ns")
    horizontal_scroll.grid(row=1, column=0, sticky="ew")
    return container, tree
