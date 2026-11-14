from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

NAVY = "#101828"
NAVY_SOFT = "#172554"
INDIGO = "#5965D8"
BLUE = INDIGO
TEAL = "#16B8A6"
CYAN = "#22D3EE"
PALE = "#F5F7FB"
WHITE = "#FFFFFF"
SURFACE = "#FFFFFF"
TEXT = "#182230"
MUTED = "#667085"
LINE = "#E7EAF0"
GREEN = "#159B75"
GREEN_PALE = "#ECFDF5"
AMBER = "#F59E0B"
AMBER_PALE = "#FFFBEB"
RED = "#EF4444"
RED_PALE = "#FEF2F2"
VIOLET = "#8B5CF6"
FONT_FAMILY = "Segoe UI"


def font_family() -> str:
    return FONT_FAMILY


def _scaled_points(points: tuple[float, ...], width: int, height: int) -> tuple[float, ...]:
    scale = min(width, height) / 24
    offset_x = (width - 24 * scale) / 2
    offset_y = (height - 24 * scale) / 2
    return tuple(
        (offset_x + point * scale) if index % 2 == 0 else (offset_y + point * scale)
        for index, point in enumerate(points)
    )


def draw_icon(canvas: tk.Canvas, name: str, color: str) -> None:
    canvas.delete("all")
    width = max(int(float(canvas.cget("width"))), 16)
    height = max(int(float(canvas.cget("height"))), 16)
    stroke = max(min(width, height) / 12, 1.6)

    def line(*points: float) -> None:
        canvas.create_line(
            *_scaled_points(tuple(points), width, height),
            fill=color,
            width=stroke,
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND,
        )

    def rect(x1: float, y1: float, x2: float, y2: float) -> None:
        canvas.create_rectangle(
            *_scaled_points((x1, y1, x2, y2), width, height),
            outline=color,
            width=stroke,
        )

    def oval(x1: float, y1: float, x2: float, y2: float) -> None:
        canvas.create_oval(
            *_scaled_points((x1, y1, x2, y2), width, height),
            outline=color,
            width=stroke,
        )

    if name == "dashboard":
        rect(3, 3, 11, 11)
        rect(14, 3, 21, 8)
        rect(14, 11, 21, 21)
        rect(3, 14, 11, 21)
    elif name == "users":
        oval(9, 3, 15, 9)
        oval(2, 7, 8, 13)
        oval(16, 7, 22, 13)
        line(6, 20, 7, 16, 9, 13, 12, 12, 15, 13, 17, 16, 18, 20)
        line(2, 20, 3, 17, 5, 15, 7, 15)
        line(17, 15, 19, 15, 21, 17, 22, 20)
    elif name in ("calendar", "calendar-check"):
        line(7, 3, 7, 7)
        line(17, 3, 17, 7)
        line(4, 9, 20, 9)
        line(4, 6, 20, 6, 20, 20, 4, 20, 4, 6)
        if name == "calendar-check":
            line(7, 14, 10, 17, 16, 11)
        else:
            oval(7, 12, 9, 14)
            oval(15, 12, 17, 14)
    elif name == "timer":
        oval(4, 6, 20, 22)
        line(12, 2, 12, 5)
        line(9, 2, 15, 2)
        line(12, 10, 12, 14, 16, 16)
        line(18, 5, 20, 3)
    elif name == "shield":
        line(12, 2, 20, 5, 19, 13, 16, 18, 12, 22, 8, 18, 5, 13, 4, 5, 12, 2)
        line(8, 12, 11, 15, 16, 9)
    elif name == "chart":
        line(3, 21, 3, 4)
        line(3, 21, 22, 21)
        rect(6, 13, 10, 20)
        rect(12, 9, 16, 20)
        rect(18, 5, 22, 20)
    elif name == "bell":
        line(5, 17, 7, 15, 7, 10, 8, 6, 12, 4, 16, 6, 17, 10, 17, 15, 19, 17, 5, 17)
        line(9, 19, 10, 21, 12, 22, 14, 21, 15, 19)
    elif name == "user":
        oval(8, 3, 16, 11)
        line(4, 21, 5, 17, 8, 14, 12, 13, 16, 14, 19, 17, 20, 21)
    elif name == "search":
        oval(3, 3, 16, 16)
        line(14, 14, 21, 21)
    elif name == "plus":
        line(12, 4, 12, 20)
        line(4, 12, 20, 12)
    elif name == "pencil":
        line(4, 18, 5, 13, 16, 2, 21, 7, 10, 18, 4, 18)
        line(14, 4, 19, 9)
    elif name == "trash":
        line(4, 6, 20, 6)
        line(9, 3, 15, 3)
        line(6, 7, 7, 21, 17, 21, 18, 7)
        line(10, 10, 10, 18)
        line(14, 10, 14, 18)
    elif name == "filter":
        line(3, 5, 21, 5, 14, 13, 14, 20, 10, 18, 10, 13, 3, 5)
    elif name == "file-up":
        line(7, 3, 15, 3, 20, 8, 20, 21, 5, 21, 5, 3, 7, 3)
        line(15, 3, 15, 8, 20, 8)
        line(12, 19, 12, 12)
        line(9, 15, 12, 12, 15, 15)
        line(9, 18, 9, 19, 15, 19, 15, 18)
    elif name == "file-down":
        line(7, 3, 15, 3, 20, 8, 20, 21, 5, 21, 5, 3, 7, 3)
        line(15, 3, 15, 8, 20, 8)
        line(12, 11, 12, 18)
        line(9, 15, 12, 18, 15, 15)
        line(9, 19, 9, 20, 15, 20, 15, 19)
    elif name == "refresh":
        line(20, 7, 20, 4, 17, 4)
        line(4, 17, 4, 20, 7, 20)
        line(20, 4, 17, 7, 12, 5, 7, 7, 5, 12)
        line(4, 20, 7, 17, 12, 19, 17, 17, 19, 12)
    elif name == "check":
        line(5, 12, 10, 17, 19, 7)
    elif name == "info":
        oval(3, 3, 21, 21)
        line(12, 10, 12, 17)
        line(12, 7, 12, 7.2)
    elif name == "clock":
        oval(3, 3, 21, 21)
        line(12, 7, 12, 12, 16, 14)
    elif name == "spark":
        line(12, 2, 13, 9, 20, 10, 13, 12, 12, 20, 11, 12, 4, 10, 11, 9, 12, 2)
    else:
        oval(4, 4, 20, 20)


def create_icon_canvas(
    parent: tk.Misc,
    name: str,
    color: str,
    background: str,
    size: int = 20,
) -> tk.Canvas:
    canvas = tk.Canvas(
        parent,
        width=size,
        height=size,
        background=background,
        highlightthickness=0,
        bd=0,
    )
    draw_icon(canvas, name, color)
    return canvas


def draw_brand_mark(canvas: tk.Canvas) -> None:
    canvas.delete("all")
    canvas.create_oval(2, 2, 40, 40, fill="#1E293B", outline="#334155", width=1)
    canvas.create_line(
        10, 30, 10, 12, 20, 25, 20, 12,
        fill="#A5B4FC", width=2.8, capstyle=tk.ROUND, joinstyle=tk.ROUND,
    )
    for x, top, color in (
        (25, 26, "#64748B"),
        (28, 23, TEAL),
        (31, 19, CYAN),
    ):
        canvas.create_rectangle(
            x, top, x + 2.5, 30, fill=color, outline="", width=0
        )
    canvas.create_oval(29, 8, 34, 13, fill="#A5B4FC", outline="")


class SidebarNavItem(tk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        label: str,
        icon: str,
        command: Callable[[], None],
    ) -> None:
        super().__init__(parent, background=NAVY, height=46, cursor="hand2")
        self.label_text = label
        self.icon_name = icon
        self.command = command
        self.active = False
        self._visual_state: tuple[str, str, str] | None = None
        self.pack_propagate(False)
        self.grid_columnconfigure(2, weight=1)
        self.accent = tk.Frame(self, width=4, background=NAVY)
        self.accent.grid(row=0, column=0, sticky="ns")
        self.icon = create_icon_canvas(self, icon, "#94A3B8", NAVY, 20)
        self.icon.grid(row=0, column=1, padx=(13, 11), pady=13)
        self.text = tk.Label(
            self,
            text=label,
            background=NAVY,
            foreground="#CBD5E1",
            font=(FONT_FAMILY, 11),
            anchor="w",
        )
        self.text.grid(row=0, column=2, sticky="ew", padx=(0, 10))
        for widget in (self, self.icon, self.text, self.accent):
            widget.bind("<Button-1>", self._on_click)

    def _on_click(self, _event: tk.Event) -> None:
        self.command()

    def set_active(self, active: bool) -> None:
        self.active = active
        self._apply_state()

    def _apply_state(self) -> None:
        background = NAVY_SOFT if self.active else NAVY
        foreground = WHITE if self.active else "#CBD5E1"
        icon_color = "#A5B4FC" if self.active else "#94A3B8"
        state = (background, foreground, icon_color)
        if state == self._visual_state:
            return
        self._visual_state = state
        self.configure(background=background)
        self.accent.configure(background=INDIGO if self.active else background)
        self.text.configure(background=background, foreground=foreground)
        self.icon.configure(background=background)
        draw_icon(self.icon, self.icon_name, icon_color)


class IconActionButton(tk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        icon: str,
        command: Callable[[], None],
        primary: bool = False,
        danger: bool = False,
    ) -> None:
        self.primary = primary
        self.danger = danger
        self.command = command
        self.icon_name = icon
        background = RED_PALE if danger else INDIGO if primary else WHITE
        super().__init__(
            parent,
            background=background,
            highlightbackground=RED if danger else INDIGO if primary else LINE,
            highlightthickness=0 if primary else 1,
            cursor="hand2",
            height=36,
            padx=11,
        )
        self.foreground = RED if danger else WHITE if primary else TEXT
        self.icon_color = RED if danger else WHITE if primary else MUTED
        self.icon = create_icon_canvas(self, icon, self.icon_color, background, size=17)
        self.icon.pack(side="left", padx=(0, 7), pady=8)
        self.text = tk.Label(
            self,
            text=text,
            background=background,
            foreground=self.foreground,
            font=(FONT_FAMILY, 10, "bold"),
        )
        self.text.pack(side="left", pady=8)
        for widget in (self, self.icon, self.text):
            widget.bind("<Button-1>", self._on_click)

    def _on_click(self, _event: tk.Event) -> None:
        self.command()

def configure_styles(root: tk.Tk) -> None:
    global FONT_FAMILY
    available_fonts = {str(family).casefold() for family in root.tk.call("font", "families")}
    FONT_FAMILY = next(
        (font for font in ("Inter", "Aptos", "Segoe UI Variable", "Segoe UI") if font.casefold() in available_fonts),
        "TkDefaultFont",
    )

    root.configure(background=PALE)
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    style.configure(".", font=(FONT_FAMILY, 10), foreground=TEXT)
    style.configure("TFrame", background=PALE)
    style.configure("Card.TFrame", background=WHITE)
    style.configure("TLabel", background=PALE, foreground=TEXT)
    style.configure("Card.TLabel", background=WHITE, foreground=TEXT)
    style.configure("CardSubtitle.TLabel", background=WHITE, foreground=MUTED, font=(FONT_FAMILY, 9))
    style.configure("Eyebrow.TLabel", background=PALE, foreground=INDIGO, font=(FONT_FAMILY, 9, "bold"))
    style.configure("Title.TLabel", background=PALE, foreground=NAVY, font=(FONT_FAMILY, 24, "bold"))
    style.configure("Subtitle.TLabel", background=PALE, foreground=MUTED, font=(FONT_FAMILY, 10))
    style.configure("Section.TLabel", background=WHITE, foreground=TEXT, font=(FONT_FAMILY, 12, "bold"))
    style.configure(
        "TButton",
        padding=(12, 8),
        background=WHITE,
        foreground=TEXT,
        borderwidth=1,
        bordercolor=LINE,
        relief="flat",
        font=(FONT_FAMILY, 10, "bold"),
    )
    style.map("TButton", foreground=[("disabled", MUTED)])
    style.configure("Accent.TButton", padding=(14, 9), background=INDIGO, foreground=WHITE, borderwidth=0, bordercolor=INDIGO)
    style.map("Accent.TButton", foreground=[("disabled", "#E6EAFB")])
    style.configure("Subtle.TButton", padding=(10, 7), background=PALE, foreground=MUTED, borderwidth=0, font=(FONT_FAMILY, 10, "bold"))
    style.configure("Danger.TButton", padding=(11, 8), background=RED_PALE, foreground=RED, borderwidth=1, bordercolor="#FECACA", relief="flat", font=(FONT_FAMILY, 10, "bold"))
    style.configure("Sidebar.TFrame", background=NAVY)
    style.configure("SidebarTitle.TLabel", background=NAVY, foreground=WHITE, font=(FONT_FAMILY, 12, "bold"))
    style.configure("SidebarCaption.TLabel", background=NAVY, foreground="#94A3B8", font=(FONT_FAMILY, 9))
    style.configure(
        "Sidebar.Vertical.TScrollbar",
        background=NAVY_SOFT,
        troughcolor=NAVY,
        bordercolor=NAVY,
        arrowcolor="#94A3B8",
    )
    style.configure("Treeview", background=WHITE, fieldbackground=WHITE, foreground=TEXT, rowheight=38, borderwidth=0, font=(FONT_FAMILY, 10))
    style.configure("Treeview.Heading", background="#F8FAFC", foreground="#64748B", font=(FONT_FAMILY, 9, "bold"), padding=(10, 10), relief="flat")
    style.map("Treeview", background=[("selected", "#EEF2FF")], foreground=[("selected", NAVY_SOFT)])
    style.configure("TEntry", padding=(9, 8), fieldbackground=WHITE, foreground=TEXT, font=(FONT_FAMILY, 11), bordercolor=LINE, lightcolor=LINE, darkcolor=LINE, insertcolor=TEXT)
    style.map("TEntry", bordercolor=[("focus", INDIGO)], lightcolor=[("focus", INDIGO)], darkcolor=[("focus", INDIGO)])
    style.configure("TCombobox", padding=(8, 7), fieldbackground=WHITE, background=WHITE, foreground=TEXT, arrowcolor=MUTED, font=(FONT_FAMILY, 10))
    style.map("TCombobox", fieldbackground=[("readonly", WHITE)], foreground=[("readonly", TEXT)])
    style.configure("TLabelframe", background=WHITE, bordercolor=LINE, relief="solid", borderwidth=1, padding=10)
    style.configure("TLabelframe.Label", background=WHITE, foreground=TEXT, font=(FONT_FAMILY, 9, "bold"))
    style.configure("TCheckbutton", background=WHITE, foreground=TEXT, font=(FONT_FAMILY, 9))
    style.configure("TSeparator", background=LINE)


def create_stat_card(
    parent: tk.Misc,
    title: str,
    value: int | str,
    icon: str,
    accent: str = BLUE,
    detail: str = "Datos registrados",
) -> tk.Frame:
    badge_background = {
        BLUE: "#EEF2FF",
        INDIGO: "#EEF2FF",
        TEAL: "#ECFEFF",
        GREEN: GREEN_PALE,
        AMBER: AMBER_PALE,
        RED: RED_PALE,
        VIOLET: "#F5F3FF",
    }.get(accent, "#EEF2FF")
    border = tk.Frame(parent, background=LINE, padx=1, pady=1)
    card = tk.Frame(border, background=WHITE, padx=15, pady=12, cursor="hand2")
    card.pack(fill="both", expand=True)
    accent_bar = tk.Frame(card, background=accent, height=3)
    accent_bar.pack(fill="x", pady=(0, 8))

    content = tk.Frame(card, background=WHITE)
    content.pack(fill="both", expand=True)
    top = tk.Frame(content, background=WHITE)
    top.pack(fill="x")
    tk.Label(top, text=title, background=WHITE, foreground=MUTED, font=(FONT_FAMILY, 9, "bold"), anchor="w").pack(side="left", fill="x", expand=True)
    icon_badge = tk.Frame(top, background=badge_background, padx=6, pady=5)
    icon_badge.pack(side="right", padx=(5, 0))
    icon_canvas = create_icon_canvas(icon_badge, icon, accent, badge_background, size=21)
    icon_canvas.pack()
    value_label = tk.Label(content, text=str(value), background=WHITE, foreground=NAVY, font=(FONT_FAMILY, 27, "bold"), anchor="w")
    value_label.pack(anchor="w", pady=(6, 1))
    tk.Label(content, text=detail, background=WHITE, foreground=MUTED, font=(FONT_FAMILY, 9), anchor="w").pack(anchor="w")
    card.value_label = value_label  # type: ignore[attr-defined]

    return border


def create_panel(parent: tk.Misc, padding: int = 14) -> tuple[tk.Frame, tk.Frame]:
    border = tk.Frame(parent, background=LINE, padx=1, pady=1)
    body = tk.Frame(border, background=WHITE, padx=padding, pady=padding)
    body.pack(fill="both", expand=True)
    return border, body


def badge(parent: tk.Misc, text: str, foreground: str, background: str) -> tk.Label:
    return tk.Label(
        parent,
        text=text,
        background=background,
        foreground=foreground,
        font=(FONT_FAMILY, 8, "bold"),
        padx=8,
        pady=3,
    )
