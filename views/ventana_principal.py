from __future__ import annotations

import csv
import os
import queue
import sqlite3
import threading
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from database import Database
from modules.asistencia import AttendanceService, ImportDataset
from modules.empleados import EmployeeService
from modules.horas_extras import OvertimeService, SHIFT_TYPES
from modules.permisos import PermissionService, STATUSES
from modules.reportes import ReportService
from views.estilos import (
    AMBER,
    AMBER_PALE,
    BLUE,
    GREEN,
    GREEN_PALE,
    IconActionButton,
    INDIGO,
    LINE,
    MUTED,
    NAVY,
    NAVY_SOFT,
    PALE,
    RED,
    RED_PALE,
    TEAL,
    TEXT,
    WHITE,
    SidebarNavItem,
    badge,
    configure_styles,
    create_icon_canvas,
    create_panel,
    create_stat_card,
    draw_brand_mark,
    draw_icon,
    font_family,
)

class MainWindow:
    PAGES = {
        "Panel principal": "dashboard",
        "Empleados": "users",
        "Asistencia": "calendar-check",
        "Permisos": "calendar-check",
        "Horas extras": "clock",
        "Validaciones": "shield",
        "Informes y consultas": "chart",
    }

    def __init__(self, root: tk.Tk, database: Database) -> None:
        self.root = root
        self.database = database
        self.employees = EmployeeService(database)
        self.attendance = AttendanceService(database)
        self.permissions = PermissionService(database)
        self.overtime = OvertimeService(database)
        self.reports = ReportService(database)
        self.current_page = "Panel principal"
        self.editing_permission_id: int | None = None
        self.editing_overtime_id: int | None = None
        self._toast_after_id: str | None = None
        configure_styles(root)
        root.title("NEXORA HR · Control de Asistencia y Novedades Laborales")
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        window_width = min(1400, max(720, screen_width - 40))
        window_height = min(820, max(520, screen_height - 80))
        root.geometry(f"{window_width}x{window_height}")
        root.minsize(min(1160, window_width), min(620, window_height))
        root.protocol("WM_DELETE_WINDOW", self.close)

        shell = ttk.Frame(root)
        shell.pack(fill="both", expand=True)
        self.sidebar = ttk.Frame(shell, style="Sidebar.TFrame", width=245)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self.workspace = ttk.Frame(shell, padding=(22, 16, 22, 16))
        self.workspace.pack(side="left", fill="both", expand=True)

        brand = tk.Frame(self.sidebar, background=NAVY)
        brand.pack(fill="x", padx=18, pady=(22, 24))
        logo = tk.Canvas(brand, width=42, height=42, background=NAVY, highlightthickness=0)
        draw_brand_mark(logo)
        logo.pack(side="left")
        brand_text = tk.Frame(brand, background=NAVY)
        brand_text.pack(side="left", padx=(10, 0))
        ttk.Label(brand_text, text="NEXORA HR", style="SidebarTitle.TLabel").pack(anchor="w")
        ttk.Label(brand_text, text="Gestión inteligente de\nasistencia y novedades", style="SidebarCaption.TLabel", justify="left").pack(anchor="w", pady=(3, 0))

        self.nav_view = tk.Frame(self.sidebar, background=NAVY)
        self.nav_view.pack(fill="both", expand=True)
        self.nav_canvas = tk.Canvas(
            self.nav_view,
            background=NAVY,
            highlightthickness=0,
            bd=0,
        )
        self.nav_scrollbar = ttk.Scrollbar(
            self.nav_view,
            orient="vertical",
            command=self.nav_canvas.yview,
            style="Sidebar.Vertical.TScrollbar",
        )
        self.nav_canvas.configure(yscrollcommand=self.nav_scrollbar.set)
        self.nav_canvas.pack(side="left", fill="both", expand=True)
        self.nav_scrollbar.pack(side="right", fill="y")
        self.nav_content = tk.Frame(self.nav_canvas, background=NAVY)
        self._nav_content_window = self.nav_canvas.create_window(
            (0, 0), window=self.nav_content, anchor="nw"
        )
        self.nav_content.bind("<Configure>", self._update_sidebar_scrollregion)
        self.nav_canvas.bind("<Configure>", self._resize_sidebar_content)

        self.nav_buttons: dict[str, SidebarNavItem] = {}
        sections = {
            "Panel principal": "PRINCIPAL",
            "Empleados": "GESTIÓN",
            "Asistencia": "GESTIÓN",
            "Permisos": "GESTIÓN",
            "Horas extras": "GESTIÓN",
            "Validaciones": "CONTROL",
            "Informes y consultas": "ANÁLISIS",
        }
        last_section = None
        for label, icon_name in self.PAGES.items():
            section = sections[label]
            if section != last_section:
                ttk.Label(self.nav_content, text=section, style="SidebarCaption.TLabel").pack(anchor="w", padx=20, pady=(12 if last_section else 0, 7))
                last_section = section
            item = SidebarNavItem(self.nav_content, label, icon_name, command=lambda page=label: self.show_page(page))
            item.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[label] = item
        self._bind_sidebar_mousewheel(self.nav_content)

        footer = tk.Frame(self.sidebar, background=NAVY)
        footer.pack(side="bottom", fill="x", padx=18, pady=16)
        ttk.Separator(footer, orient="horizontal").pack(fill="x", pady=(0, 10))
        ttk.Label(footer, text="NEXORA HR  ·  v1.3", style="SidebarCaption.TLabel").pack(anchor="w")
        ttk.Label(footer, text="Aplicación de escritorio · datos locales", style="SidebarCaption.TLabel").pack(anchor="w", pady=(3, 0))

        header = ttk.Frame(self.workspace, style="Card.TFrame", padding=(18, 12))
        header.pack(fill="x", pady=(0, 10))
        title_block = ttk.Frame(header)
        title_block.pack(side="left", fill="x", expand=True)
        ttk.Label(title_block, text="ESPACIO DE TRABAJO", style="Eyebrow.TLabel").pack(anchor="w")
        self.page_title = ttk.Label(title_block, style="Title.TLabel")
        self.page_title.pack(anchor="w", pady=(2, 0))
        self.page_subtitle = ttk.Label(title_block, style="CardSubtitle.TLabel", wraplength=700)
        self.page_subtitle.pack(anchor="w", pady=(2, 0))

        header_actions = ttk.Frame(header, style="Card.TFrame")
        header_actions.pack(side="right", anchor="center", padx=(14, 0))
        self.date_label = ttk.Label(header_actions, text=self._spanish_today(), style="Card.TLabel", anchor="e")
        self.date_label.pack(side="left", anchor="center", padx=(0, 12))
        self.alert_button = tk.Frame(header_actions, background=PALE, cursor="hand2", padx=9, pady=6)
        self.alert_button.pack(side="left", padx=(0, 10))
        self.alert_icon = create_icon_canvas(self.alert_button, "bell", MUTED, PALE, size=17)
        self.alert_icon.pack(side="left", padx=(0, 6))
        self.alert_count_label = tk.Label(self.alert_button, text="0", background=PALE, foreground=MUTED, font=(font_family(), 8, "bold"))
        self.alert_count_label.pack(side="left")
        for widget in (self.alert_button, self.alert_icon, self.alert_count_label):
            widget.bind("<Button-1>", lambda _event: self.show_page("Validaciones"))

        profile = tk.Frame(header_actions, background=WHITE, highlightbackground=LINE, highlightthickness=1, padx=9, pady=5)
        profile.pack(side="left")
        avatar = tk.Canvas(profile, width=30, height=30, background="#EEF2FF", highlightthickness=0)
        draw_icon(avatar, "user", INDIGO)
        avatar.pack(side="left", padx=(0, 7))
        user_label = ttk.Frame(profile, style="Card.TFrame")
        user_label.pack(side="left")
        ttk.Label(user_label, text="Usuario local", style="Card.TLabel", font=(font_family(), 8, "bold")).pack(anchor="w")
        ttk.Label(user_label, text="Sesión de prototipo", style="CardSubtitle.TLabel").pack(anchor="w")

        ttk.Separator(self.workspace, orient="horizontal").pack(fill="x", pady=(0, 10))
        page_container = ttk.Frame(self.workspace)
        page_container.pack(fill="both", expand=True)
        self.page_canvas = tk.Canvas(
            page_container,
            background=PALE,
            highlightthickness=0,
            bd=0,
        )
        self.page_scrollbar = ttk.Scrollbar(
            page_container,
            orient="vertical",
            command=self.page_canvas.yview,
        )
        self.page_content = ttk.Frame(self.page_canvas)
        self._page_content_window = self.page_canvas.create_window(
            (0, 0), window=self.page_content, anchor="nw"
        )
        self.page_canvas.configure(yscrollcommand=self.page_scrollbar.set)
        self.page_canvas.pack(side="left", fill="both", expand=True)
        self.page_scrollbar.pack(side="right", fill="y")
        self.page_content.bind("<Configure>", self._update_page_scrollregion)
        self.page_canvas.bind("<Configure>", self._resize_page_content)
        root.bind_all("<MouseWheel>", self._scroll_page_content, add="+")
        self.toast = tk.Label(self.workspace, text="", font=(font_family(), 9, "bold"), padx=16, pady=10, bd=0)
        self.show_page("Panel principal")

    def _update_sidebar_scrollregion(self, _event: tk.Event | None = None) -> None:
        self.nav_canvas.configure(scrollregion=self.nav_canvas.bbox("all"))

    def _resize_sidebar_content(self, event: tk.Event) -> None:
        self.nav_canvas.itemconfigure(self._nav_content_window, width=event.width)

    def _update_page_scrollregion(self, _event: tk.Event | None = None) -> None:
        self.page_canvas.configure(scrollregion=self.page_canvas.bbox("all"))

    def _resize_page_content(self, event: tk.Event) -> None:
        self.page_canvas.itemconfigure(self._page_content_window, width=event.width)

    @staticmethod
    def _wheel_steps(event: tk.Event) -> int:
        steps = int(-event.delta / 120)
        if steps == 0:
            return -1 if event.delta > 0 else 1
        return steps

    def _scroll_page_content(self, event: tk.Event) -> str:
        self.page_canvas.yview_scroll(MainWindow._wheel_steps(event), "units")
        return "break"

    def _scroll_table(self, event: tk.Event) -> str:
        event.widget.yview_scroll(MainWindow._wheel_steps(event), "units")
        return "break"

    def _scroll_table_horizontally(self, event: tk.Event) -> str:
        event.widget.xview_scroll(MainWindow._wheel_steps(event), "units")
        return "break"

    def _bind_table_scroll(self, tree: ttk.Treeview) -> None:
        tree.bind("<MouseWheel>", self._scroll_table, add="+")
        tree.bind("<Shift-MouseWheel>", self._scroll_table_horizontally, add="+")

    def _bind_sidebar_mousewheel(self, widget: tk.Misc) -> None:
        widget.bind("<MouseWheel>", self._scroll_sidebar, add="+")
        for child in widget.winfo_children():
            self._bind_sidebar_mousewheel(child)

    def _scroll_sidebar(self, event: tk.Event) -> str:
        steps = int(-event.delta / 120)
        if steps == 0:
            steps = -1 if event.delta > 0 else 1
        self.nav_canvas.yview_scroll(steps, "units")
        return "break"

    def show_page(self, page: str) -> None:
        if page not in self.PAGES:
            raise ValueError(f"Módulo desconocido: {page}")
        self.current_page = page
        self._refresh_notification_badge()
        for child in self.page_content.winfo_children():
            child.destroy()
        self.page_canvas.yview_moveto(0)
        for label, button in self.nav_buttons.items():
            button.set_active(label == page)
        self.page_title.configure(text=page)
        builders: dict[str, tuple[str, Callable[[], None]]] = {
            "Panel principal": ("Resumen visual, indicadores clave y accesos rápidos basados en datos locales.", self._build_dashboard),
            "Empleados": ("Administre códigos internos y datos laborales mínimos con acciones seguras.", self._build_employees),
            "Asistencia": ("Registre, importe, consulte y revise marcaciones con validaciones informativas.", self._build_attendance),
            "Permisos": ("Gestione solicitudes y seguimiento de estado con campos de referencia F-012.", self._build_permissions),
            "Horas extras": ("Registre horas extra reportadas y autorizaciones sin cálculos de nómina.", self._build_overtime),
            "Validaciones": ("Revise observaciones y alertas informativas para verificación manual.", self._build_validations),
            "Informes y consultas": ("Filtre, consulte y exporte resultados en CSV o Excel.", self._build_reports),
        }
        subtitle, builder = builders[page]
        self.page_subtitle.configure(text=subtitle)
        builder()

    def _refresh_notification_badge(self, refresh: bool = False) -> None:
        if not hasattr(self, "alert_count_label"):
            return
        if refresh or not hasattr(self, "_notification_count"):
            self._notification_count = sum(bool(record["alerts"]) for record in self.attendance.list())
        alert_count = self._notification_count
        self.alert_count_label.configure(text=str(alert_count), foreground=RED if alert_count else MUTED, background=PALE)
        draw_icon(self.alert_icon, "bell", RED if alert_count else MUTED)

    @staticmethod
    def _spanish_today() -> str:
        weekdays = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
        months = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")
        today = date.today()
        return f"{weekdays[today.weekday()]}, {today.day} de {months[today.month - 1]} de {today.year}"

    def _draw_dashboard_illustration(self, event: tk.Event) -> None:
        canvas = self.hero_canvas
        canvas.delete("dashboard-art")
        if event.width < 680:
            return

        center_x = event.width - 178
        canvas.create_oval(
            center_x - 104,
            -50,
            center_x + 92,
            154,
            fill="#172554",
            outline="#263455",
            width=2,
            tags="dashboard-art",
        )
        canvas.create_rectangle(
            center_x - 70,
            26,
            center_x + 70,
            101,
            fill="#202E4D",
            outline="#334155",
            width=1,
            tags="dashboard-art",
        )
        canvas.create_rectangle(
            center_x - 54,
            39,
            center_x - 20,
            43,
            fill="#94A3B8",
            outline="",
            tags="dashboard-art",
        )
        canvas.create_rectangle(
            center_x - 54,
            49,
            center_x + 45,
            51,
            fill="#475569",
            outline="",
            tags="dashboard-art",
        )
        for offset, top, color in (
            (-42, 75, "#5965D8"),
            (-18, 66, "#16B8A6"),
            (6, 58, "#22D3EE"),
            (30, 48, "#A5B4FC"),
        ):
            canvas.create_rectangle(
                center_x + offset,
                top,
                center_x + offset + 12,
                91,
                fill=color,
                outline="",
                tags="dashboard-art",
            )
        canvas.create_line(
            center_x - 46,
            68,
            center_x - 21,
            61,
            center_x + 1,
            65,
            center_x + 27,
            47,
            fill="#FFFFFF",
            width=2,
            smooth=True,
            tags="dashboard-art",
        )
        for x, y in (
            (center_x - 46, 68),
            (center_x - 21, 61),
            (center_x + 1, 65),
            (center_x + 27, 47),
        ):
            canvas.create_oval(
                x - 3,
                y - 3,
                x + 3,
                y + 3,
                fill=TEAL,
                outline=WHITE,
                width=1,
                tags="dashboard-art",
            )

    def _build_dashboard(self) -> None:
        summary = self.reports.summary()
        attendance = self.attendance.list()
        self.dashboard_attendance = attendance
        employees = self.employees.list()
        incomplete = sum(bool(record["alerts"]) for record in attendance)
        active_employees = sum(bool(employee["active"]) for employee in employees)
        permission_records = self.permissions.list()
        overtime_records = self.overtime.list()
        self.dashboard_novelties = (
            ("Pendientes", sum(item["status"] == "Pendiente" for item in permission_records), AMBER),
            ("Aprobados", sum(item["status"] == "Aprobado" for item in permission_records), GREEN),
            ("Rechazados", sum(item["status"] == "Rechazado" for item in permission_records), RED),
            ("Horas extra", len(overtime_records), INDIGO),
        )
        hour = datetime.now().hour
        greeting = "Buenos días" if hour < 12 else "Buenas tardes" if hour < 19 else "Buenas noches"

        hero_border, hero = create_panel(self.page_content, padding=0)
        hero_border.pack(fill="x", pady=(0, 12))
        hero_canvas = tk.Canvas(hero, height=124, background=NAVY, highlightthickness=0)
        hero_canvas.pack(fill="x")
        self.hero_canvas = hero_canvas
        hero_canvas.create_text(24, 28, anchor="nw", text=f"{greeting}, bienvenido a NEXORA HR", fill=WHITE, font=(font_family(), 18, "bold"))
        hero_canvas.create_text(24, 62, anchor="nw", text="Monitorea asistencia, permisos y horas extra con una vista clara y moderna.", fill="#CBD5E1", font=(font_family(), 10))
        hero_canvas.create_text(24, 98, anchor="nw", text=f"Hoy: {self._spanish_today()}  •  Registros para revisar: {incomplete}", fill="#A5B4FC", font=(font_family(), 9, "bold"))
        hero_canvas.bind("<Configure>", self._draw_dashboard_illustration)

        quick = ttk.Frame(self.page_content, style="Card.TFrame")
        quick.pack(fill="x", pady=(0, 12))
        self.dashboard_quick_actions = quick
        for text, icon, page, primary in (
            ("Nueva marcación", "plus", "Asistencia", True),
            ("Registrar permiso", "calendar-check", "Permisos", False),
            ("Ver validaciones", "shield", "Validaciones", False),
        ):
            IconActionButton(
                quick, text, icon, lambda p=page: self.show_page(p), primary=primary
            ).pack(side="left", padx=(10, 4), pady=8)

        cards = ttk.Frame(self.page_content)
        cards.pack(fill="x", pady=(0, 12))
        metrics = (
            ("Total de empleados", len(employees), "users", INDIGO, f"{active_employees} activos"),
            ("Registros de asistencia", summary["attendance"], "calendar", TEAL, "Marcaciones guardadas"),
            ("Permisos pendientes", summary["permissions_pending"], "calendar-check", AMBER, "Por gestionar"),
            ("Horas extras", summary["overtime"], "timer", GREEN, "Registros reportados"),
            ("Registros por revisar", incomplete, "shield", RED, "Alertas informativas"),
        )
        self.dashboard_cards = []
        for index, (label, value, icon, color, detail) in enumerate(metrics):
            card = create_stat_card(cards, label, value, icon, color, detail)
            card.grid(row=0, column=index, padx=(0, 8 if index < len(metrics) - 1 else 0), sticky="nsew")
            cards.columnconfigure(index, weight=1)
            self.dashboard_cards.append(card)

        charts = ttk.Frame(self.page_content)
        charts.pack(fill="both", expand=True, pady=(0, 12))
        for builder_name, title, subtitle, attr in (
            ("_draw_attendance_chart", "Estado de marcaciones", "Completas vs por revisar", "attendance_chart"),
            ("_draw_weekly_chart", "Actividad semanal", "Marcaciones en los últimos 7 días", "weekly_chart"),
            ("_draw_novelty_chart", "Resumen de novedades", "Permisos y horas extra", "novelty_chart"),
        ):
            border, panel = create_panel(charts, padding=12)
            border.pack(side="left", fill="both", expand=True, padx=(0, 8 if attr != "novelty_chart" else 0))
            ttk.Label(panel, text=title, style="Section.TLabel").pack(anchor="w")
            ttk.Label(panel, text=subtitle, style="CardSubtitle.TLabel").pack(anchor="w", pady=(2, 4))
            canvas = tk.Canvas(panel, height=165, background=WHITE, highlightthickness=0)
            canvas.pack(fill="both", expand=True)
            setattr(self, attr, canvas)
            if attr == "weekly_chart":
                canvas.bind("<Configure>", lambda e, c=canvas: self._draw_weekly_chart(c.winfo_width(), c.winfo_height(), attendance))
                canvas.after_idle(lambda c=canvas: self._draw_weekly_chart(c.winfo_width(), c.winfo_height(), attendance))
            elif attr == "attendance_chart":
                canvas.bind("<Configure>", lambda e, c=canvas: self._draw_attendance_chart(c.winfo_width(), c.winfo_height()))
                canvas.after_idle(lambda c=canvas: self._draw_attendance_chart(c.winfo_width(), c.winfo_height()))
            else:
                canvas.bind("<Configure>", lambda e, c=canvas: self._draw_novelty_chart(c.winfo_width(), c.winfo_height()))
                canvas.after_idle(lambda c=canvas: self._draw_novelty_chart(c.winfo_width(), c.winfo_height()))

        activity_border, activity = create_panel(self.page_content, padding=11)
        activity_border.pack(fill="x")
        heading = ttk.Frame(activity)
        heading.pack(fill="x")
        ttk.Label(heading, text="Actividad reciente", style="Section.TLabel").pack(side="left")
        ttk.Button(heading, text="Actualizar", style="Subtle.TButton", command=lambda: self.show_page("Panel principal")).pack(side="right", padx=(6, 0))
        ttk.Button(heading, text="Ver alertas", style="Subtle.TButton", command=lambda: self.show_page("Validaciones")).pack(side="right")
        recent = self._dashboard_recent_activity(attendance, permission_records, overtime_records)
        if not recent:
            ttk.Label(activity, text="Todavía no hay actividad registrada. Comienza agregando empleados y marcaciones.", style="CardSubtitle.TLabel", wraplength=900).pack(anchor="w", pady=(10, 2))
        else:
            rows = ttk.Frame(activity)
            rows.pack(fill="x", pady=(6, 0))
            for index, item in enumerate(recent):
                row = tk.Frame(rows, background="#F8FAFC" if index % 2 == 0 else WHITE, padx=8, pady=6)
                row.grid(row=index, column=0, sticky="ew", pady=2)
                icon = create_icon_canvas(row, item["icon"], item["color"], row.cget("background"), size=17)
                icon.pack(side="left", padx=(0, 10))
                tk.Label(row, text=item["title"], background=row.cget("background"), foreground=TEXT, font=(font_family(), 9, "bold")).pack(side="left")
                tk.Label(row, text=item["detail"], background=row.cget("background"), foreground=item["color"], font=(font_family(), 9)).pack(side="right")
            rows.columnconfigure(0, weight=1)

    def _build_validations(self) -> None:
        records = [record for record in self.attendance.list() if record["alerts"]]
        missing_entry = sum("Falta la hora de entrada" in record["alerts"] for record in records)
        missing_exit = sum("Falta la hora de salida" in record["alerts"] for record in records)
        unassociated = sum("Código sin empleado asociado" in record["alerts"] for record in records)

        cards = ttk.Frame(self.page_content)
        cards.pack(fill="x", pady=(0, 12))
        for index, (title, value, icon, color) in enumerate(
            (
                ("Registros por revisar", len(records), "shield", AMBER),
                ("Sin hora de entrada", missing_entry, "calendar", RED),
                ("Sin hora de salida", missing_exit, "calendar-check", RED),
                ("Sin empleado asociado", unassociated, "users", BLUE),
            )
        ):
            card = create_stat_card(cards, title, value, icon, color, "Alerta informativa")
            card.grid(row=0, column=index, padx=(0, 9), sticky="nsew")
            cards.columnconfigure(index, weight=1)

        toolbar = ttk.Frame(self.page_content)
        toolbar.pack(fill="x", pady=(0, 9))
        self.validation_search = tk.StringVar()
        search_frame, search = self._search_bar(toolbar, self.validation_search, width=27)
        search_frame.pack(side="left", padx=(0, 8))
        search.bind("<KeyRelease>", self._on_validation_search)
        ttk.Button(toolbar, text="Actualizar lista", command=self._refresh_validations).pack(side="left")
        ttk.Button(toolbar, text="Ir a asistencia  ›", style="Accent.TButton", command=lambda: self.show_page("Asistencia")).pack(side="right")
        ttk.Label(
            self.page_content,
            text="Las alertas solicitan verificación manual; no califican una ausencia, una falta ni un error de nómina.",
            style="Subtitle.TLabel",
            wraplength=950,
        ).pack(anchor="w", pady=(0, 8))
        self.validation_tree = self._tree(
            self.page_content,
            (
                ("id", "ID", 0),
                ("employee_code", "Código", 115),
                ("employee_name", "Empleado", 190),
                ("work_date", "Fecha", 105),
                ("entry_time", "Entrada", 90),
                ("exit_time", "Salida", 90),
                ("source", "Fuente", 150),
                ("alerts", "Observaciones", 430),
            ),
        )
        self._refresh_validations()

    def _on_validation_search(self, event: tk.Event) -> None:
        if event.widget.winfo_exists():
            self._refresh_validations()

    def _refresh_validations(self) -> None:
        if not hasattr(self, "validation_tree") or not self.validation_tree.winfo_exists():
            return
        needle = self.validation_search.get().strip().casefold()
        records = [record for record in self.attendance.list() if record["alerts"]]
        if needle:
            records = [
                record
                for record in records
                if needle
                in " ".join(
                    (
                        str(record["employee_code"]),
                        str(record["employee_name"]),
                        str(record["work_date"]),
                        "; ".join(record["alerts"]),
                    )
                ).casefold()
            ]
        self._fill_tree(
            self.validation_tree,
            records,
            lambda record: (
                record["id"],
                record["employee_code"],
                record["employee_name"],
                record["work_date"],
                record["entry_time"],
                record["exit_time"],
                record["source"],
                "; ".join(record["alerts"]),
            ),
            lambda record: ("warning",) if record["alerts"] else (),
        )

    def _build_attendance(self) -> None:
        form = ttk.LabelFrame(self.page_content, text="Registrar marcación", padding=10)
        form.pack(fill="x")
        self.att_employee = self._employee_combo(form, "Empleado", 0, 0)
        self.att_date = self._form_entry(form, "Fecha (AAAA-MM-DD)", 0, 1, date.today().isoformat())
        self.att_entry = self._form_entry(form, "Entrada (HH:MM)", 1, 0)
        self.att_exit = self._form_entry(form, "Salida (HH:MM)", 1, 1)
        self.att_source = self._form_entry(form, "Fuente", 2, 0, "Registro manual")
        form_actions = ttk.Frame(form, style="Card.TFrame")
        form_actions.grid(row=3, column=0, columnspan=2, padx=6, pady=5, sticky="e")
        self.attendance_form_actions = form_actions
        IconActionButton(form_actions, text="Importar registros", icon="file-up", command=self._import_attendance).pack(side="left", padx=(0, 7))
        ttk.Button(form_actions, text="Guardar marcación", style="Accent.TButton", command=self._save_attendance).pack(side="left")
        quick_actions = ttk.Frame(form, style="Card.TFrame")
        quick_actions.grid(row=4, column=0, columnspan=2, padx=6, pady=(2, 4), sticky="w")
        ttk.Button(quick_actions, text="Marcar entrada ahora", command=lambda: self._mark_now("entry")).pack(side="left", padx=(0, 6))
        ttk.Button(quick_actions, text="Marcar salida ahora", command=lambda: self._mark_now("exit")).pack(side="left")

        filters = ttk.Frame(self.page_content, padding=(0, 10))
        filters.pack(fill="x")
        self.att_filter_employee = self._employee_combo(filters, "Filtrar empleado", 0, 0, include_all=True)
        self.att_start = self._form_entry(filters, "Desde (AAAA-MM-DD)", 0, 1)
        self.att_end = self._form_entry(filters, "Hasta (AAAA-MM-DD)", 0, 2)
        filter_actions = ttk.Frame(filters)
        filter_actions.grid(row=1, column=0, columnspan=3, padx=6, pady=4, sticky="e")
        self.attendance_filter_actions = filter_actions
        ttk.Button(filter_actions, text="Aplicar filtros", command=self._refresh_attendance).pack(side="left", padx=(0, 6))
        IconActionButton(filter_actions, text="Eliminar", icon="trash", command=self._delete_attendance, danger=True).pack(side="left", padx=(0, 6))
        IconActionButton(filter_actions, text="Exportar CSV", icon="file-down", command=self._export_attendance).pack(side="left")
        self.attendance_tree = self._tree(
            self.page_content,
            (
                ("id", "ID", 0),
                ("employee_code", "Código", 90),
                ("employee_name", "Empleado", 180),
                ("work_date", "Fecha", 100),
                ("entry_time", "Entrada", 85),
                ("exit_time", "Salida", 85),
                ("source", "Fuente", 120),
                ("import_batch_id", "Lote", 55),
                ("source_row", "Fila origen", 75),
                ("alerts", "Observaciones para revisión", 330),
            ),
        )
        self.attendance_tree.tag_configure("alert", foreground=AMBER, background="#FFFBEB")
        self._refresh_attendance()

    def _mark_now(self, kind: str) -> None:
        now = datetime.now()
        self._set_entry(self.att_date, now.strftime("%Y-%m-%d"))
        if kind == "entry":
            self._set_entry(self.att_entry, now.strftime("%H:%M"))
            self._notify("Hora de entrada completada con la hora actual.")
        else:
            self._set_entry(self.att_exit, now.strftime("%H:%M"))
            self._notify("Hora de salida completada con la hora actual.")

    def _attendance_records(self) -> list[dict[str, Any]]:
        employee_id = self._combo_id(self.att_filter_employee)
        start, end = self.att_start.get().strip(), self.att_end.get().strip()
        try:
            self.attendance.validate_period(start, end)
        except ValueError as error:
            messagebox.showwarning("Revise el periodo", str(error), parent=self.root)
            return []
        return self.attendance.list(employee_id, start, end)

    def _refresh_attendance(self) -> None:
        if not hasattr(self, "attendance_tree") or not self.attendance_tree.winfo_exists():
            return
        records = self._attendance_records()
        self._fill_tree(
            self.attendance_tree,
            records,
            lambda record: (
                record["id"], record["employee_code"], record["employee_name"],
                record["work_date"], record["entry_time"], record["exit_time"],
                record["source"], record["import_batch_id"] or "",
                record["source_row"] or "", "; ".join(record["alerts"]),
            ),
            lambda record: ("alert",) if record["alerts"] else (),
        )

    def _save_attendance(self) -> None:
        code = self._combo_code(self.att_employee)
        try:
            self.attendance.add(
                code, self.att_date.get(), self.att_entry.get(),
                self.att_exit.get(), self.att_source.get(),
            )
        except sqlite3.Error as error:
            messagebox.showerror("No se pudo guardar", str(error), parent=self.root)
            return
        self._refresh_attendance()
        self._refresh_dashboard_if_visible()
        self._notify("Marcación guardada. Las observaciones quedan disponibles para revisión.")

    def _delete_attendance(self) -> None:
        selected = self._selected_record(self.attendance_tree)
        if not selected:
            return
        record_id = int(selected[0])
        record = next((item for item in self.attendance.list() if item["id"] == record_id), None)
        if record is None:
            messagebox.showwarning("Registro no disponible", "La marcación seleccionada ya no existe.", parent=self.root)
            self._refresh_attendance()
            return
        if not messagebox.askyesno(
            "Eliminar marcación",
            f"¿Eliminar la marcación de {record['employee_name']} del {record['work_date']}? Esta acción no se puede deshacer.",
            parent=self.root,
        ):
            return
        try:
            self.attendance.delete(record_id)
        except (ValueError, sqlite3.Error) as error:
            messagebox.showerror("No se pudo eliminar la marcación", str(error), parent=self.root)
            return
        self._refresh_attendance()
        self._refresh_dashboard_if_visible()
        self._notify("Marcación eliminada.")

    def _import_attendance(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Seleccionar archivo de asistencia",
            filetypes=(
                ("CSV y Excel", "*.csv *.xlsx"),
                ("Archivo CSV", "*.csv"),
                ("Excel", "*.xlsx"),
            ),
        )
        if not path:
            return
        selected = Path(path)
        try:
            sheet_names = self.attendance.available_sheets(selected)
        except (OSError, ValueError, RuntimeError) as error:
            messagebox.showerror("No se pudo leer el archivo", str(error), parent=self.root)
            return

        dialog = self._dialog("Revisar importación de asistencia")
        dialog.resizable(True, True)
        dialog.geometry("1080x700")
        dialog.minsize(940, 600)
        body = ttk.Frame(dialog, padding=16)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=f"Archivo: {selected.name}", style="Section.TLabel").pack(anchor="w")
        ttk.Label(
            body,
            text=(
                "Revise el mapeo y la vista previa antes de guardar. La fuente y los valores originales se conservan; "
                "fechas y horas reconocidas se normalizan solo en los campos de consulta. La aplicación no autentica la fuente: "
                "marque original verificado solo si cuenta con evidencia."
            ),
            style="Subtitle.TLabel",
            wraplength=1000,
        ).pack(anchor="w", pady=(3, 10))

        source_row = ttk.Frame(body)
        source_row.pack(fill="x", pady=(0, 7))
        ttk.Label(source_row, text="Hoja de Excel:").pack(side="left")
        sheet_var = tk.StringVar(value=sheet_names[0])
        sheet_combo = ttk.Combobox(source_row, textvariable=sheet_var, values=sheet_names, state="readonly", width=28)
        sheet_combo.pack(side="left", padx=(7, 18))
        if selected.suffix.lower() != ".xlsx":
            sheet_combo.configure(state="disabled")
        ttk.Label(source_row, text="Clasificación de fuente:").pack(side="left")
        source_labels = {
            "No verificada": "no_verificada",
            "Original verificado": "original_verificado",
            "Transcripción documental": "transcripcion_documental",
            "Datos sintéticos": "datos_sinteticos",
        }
        source_type_combo = ttk.Combobox(source_row, values=tuple(source_labels), state="readonly", width=28)
        source_type_combo.set("No verificada")
        source_type_combo.pack(side="left", padx=7)

        mapping_frame = ttk.LabelFrame(body, text="Relación de columnas", padding=8)
        mapping_frame.pack(fill="x", pady=(0, 8))
        mapping_definitions = (
            ("employee_code", "Código interno del empleado"),
            ("work_date", "Fecha"),
            ("entry_time", "Hora de entrada"),
            ("exit_time", "Hora de salida"),
        )
        mapping_vars: dict[str, tk.StringVar] = {}
        mapping_combos: dict[str, ttk.Combobox] = {}
        for column, (field, label) in enumerate(mapping_definitions):
            cell = ttk.Frame(mapping_frame, style="Card.TFrame")
            cell.grid(row=0, column=column, padx=5, pady=4, sticky="ew")
            mapping_frame.columnconfigure(column, weight=1)
            ttk.Label(cell, text=label, style="Card.TLabel").pack(anchor="w")
            variable = tk.StringVar()
            combo = ttk.Combobox(cell, textvariable=variable, state="readonly")
            combo.pack(fill="x", pady=(2, 0))
            mapping_vars[field] = variable
            mapping_combos[field] = combo

        group_frame = ttk.LabelFrame(body, text="Asociación manual de empleados del reporte", padding=8)
        group_tree = ttk.Treeview(group_frame, columns=("group", "employee", "code"), show="headings", height=4, selectmode="browse")
        group_tree.heading("group", text="Bloque")
        group_tree.heading("employee", text="Grupo del archivo")
        group_tree.heading("code", text="Código interno asignado")
        group_tree.column("group", width=65, stretch=False)
        group_tree.column("employee", width=360)
        group_tree.column("code", width=190)
        group_tree.pack(side="left", fill="both", expand=True)
        group_scroll = ttk.Scrollbar(group_frame, orient="vertical", command=group_tree.yview)
        group_scroll.pack(side="left", fill="y")
        group_tree.configure(yscrollcommand=group_scroll.set)
        registered_codes = [item["code"] for item in self.employees.list(include_inactive=False)]
        group_code_combo = ttk.Combobox(group_frame, values=("", *registered_codes), state="readonly", width=22)
        group_code_combo.pack(side="left", padx=(10, 5), anchor="n")
        assignments: dict[str, str] = {}
        dataset: ImportDataset | None = None
        current_preview: list[dict[str, Any]] = []

        def display_import_value(original: Any, normalized: str) -> str:
            original_text = "" if original is None else str(original)
            if original_text == normalized:
                return original_text
            return f"{original_text} → {normalized}"

        def assign_group() -> None:
            selected_items = group_tree.selection()
            if not selected_items:
                messagebox.showinfo("Seleccione un bloque", "Seleccione primero un bloque del reporte.", parent=dialog)
                return
            values = group_tree.item(selected_items[0], "values")
            group_key = str(values[0])
            code = group_code_combo.get().strip()
            assignments[group_key] = code
            group_tree.item(selected_items[0], values=(values[0], values[1], code or "Sin asociación"))
            refresh_preview()

        ttk.Button(group_frame, text="Asignar código", command=assign_group).pack(side="left", padx=5, anchor="n")

        preview_header = ttk.Frame(body)
        preview_header.pack(fill="x", pady=(2, 5))
        preview_title = ttk.Label(preview_header, style="Section.TLabel")
        preview_title.pack(side="left", anchor="w")
        loading_row = ttk.Frame(preview_header)
        loading_label = ttk.Label(loading_row, text="Leyendo archivo…", style="Subtitle.TLabel")
        loading_label.pack(side="left")
        preview_container = ttk.Frame(body)
        preview_container.pack(fill="both", expand=True)
        preview_container.columnconfigure(0, weight=1)
        preview_container.rowconfigure(0, weight=1)
        preview_tree = ttk.Treeview(preview_container, columns=("employee", "date", "entry", "exit", "alerts"), show="headings", height=9)
        for key, label, width in (
            ("employee", "Empleado / código", 180),
            ("date", "Fecha (archivo → consulta)", 180),
            ("entry", "Entrada (archivo → consulta)", 170),
            ("exit", "Salida (archivo → consulta)", 170),
            ("alerts", "Validaciones para revisar", 420),
        ):
            preview_tree.heading(key, text=label)
            preview_tree.column(key, width=width, stretch=key == "alerts")
        preview_tree.grid(row=0, column=0, sticky="nsew")
        preview_scroll = ttk.Scrollbar(preview_container, orient="vertical", command=preview_tree.yview)
        preview_scroll.grid(row=0, column=1, sticky="ns")
        preview_tree.configure(yscrollcommand=preview_scroll.set)
        summary_label = ttk.Label(body, style="Subtitle.TLabel")
        summary_label.pack(anchor="w", pady=(5, 0))
        load_results: queue.Queue[tuple[int, ImportDataset | None, str | None]] = queue.Queue()
        load_generation = 0

        def refresh_preview() -> None:
            nonlocal current_preview
            if dataset is None:
                return
            mapping = {field: variable.get() for field, variable in mapping_vars.items()}
            try:
                current_preview = self.attendance.preview_import(dataset, mapping, assignments)
            except ValueError as error:
                current_preview = []
                summary_label.configure(text=str(error))
                return
            preview_tree.delete(*preview_tree.get_children())
            for record in current_preview[:100]:
                employee_text = record["employee_code"] or record["group_label"] or "Sin asociación"
                preview_tree.insert(
                    "", "end",
                    values=(
                        employee_text,
                        display_import_value(record["original_work_date"], record["work_date"]),
                        display_import_value(record["original_entry_time"], record["entry_time"]),
                        display_import_value(record["original_exit_time"], record["exit_time"]),
                        "; ".join(record["alerts"]),
                    ),
                )
            invalid_count = sum(any(not alert.startswith("Posible duplicidad:") for alert in item["alerts"]) for item in current_preview)
            duplicate_count = sum(any(alert.startswith("Posible duplicidad:") for alert in item["alerts"]) for item in current_preview)
            unmatched_count = sum(any("sin empleado asociado" in alert.lower() for alert in item["alerts"]) for item in current_preview)
            preview_title.configure(text=f"Vista previa: {min(len(current_preview), 100)} de {len(current_preview)} filas")
            summary_label.configure(text=f"Con alertas: {invalid_count} · Posibles duplicados: {duplicate_count} · Sin asociación: {unmatched_count}")

        def load_dataset(event: tk.Event | None = None) -> None:
            nonlocal dataset, load_generation
            if event is not None and event.widget is not sheet_combo:
                return
            load_generation += 1
            generation = load_generation
            dataset = None
            current_preview.clear()
            preview_tree.delete(*preview_tree.get_children())
            preview_title.configure(text="Preparando vista previa…")
            summary_label.configure(text="")
            if not loading_row.winfo_manager():
                loading_row.pack(side="right")
            sheet_combo.configure(state="disabled")
            for combo in mapping_combos.values():
                combo.configure(state="disabled")
            chosen_sheet = sheet_var.get() if selected.suffix.lower() == ".xlsx" else None

            def read_source() -> None:
                try:
                    loaded_dataset = self.attendance.read_import_source(selected, chosen_sheet)
                except (OSError, UnicodeError, csv.Error, ValueError, RuntimeError) as error:
                    load_results.put((generation, None, str(error)))
                else:
                    load_results.put((generation, loaded_dataset, None))

            def finish_loading() -> None:
                nonlocal dataset
                if not dialog.winfo_exists():
                    return
                try:
                    result_generation, loaded_dataset, error_message = load_results.get_nowait()
                except queue.Empty:
                    dialog.after(80, finish_loading)
                    return
                if result_generation != load_generation:
                    return
                loading_row.pack_forget()
                sheet_combo.configure(state="readonly" if selected.suffix.lower() == ".xlsx" else "disabled")
                if error_message is not None:
                    dataset = None
                    messagebox.showerror("No se pudo preparar la vista previa", error_message, parent=dialog)
                    preview_title.configure(text="No se pudo preparar la vista previa.")
                    return
                if loaded_dataset is None:
                    return
                dataset = loaded_dataset
                available_headers = ("", *dataset.headers)
                guessed = self.attendance.guess_mapping(dataset.headers)
                for field, combo in mapping_combos.items():
                    combo.configure(values=available_headers, state="readonly")
                    mapping_vars[field].set(guessed.get(field, ""))
                    if dataset.grouped_report and field == "employee_code":
                        mapping_vars[field].set("")
                group_tree.delete(*group_tree.get_children())
                assignments.clear()
                if dataset.groups:
                    group_frame.pack(fill="x", pady=(0, 8), before=preview_header)
                    for group_key, label in dataset.groups.items():
                        group_tree.insert("", "end", values=(group_key, label, "Sin asociación"))
                else:
                    group_frame.pack_forget()
                refresh_preview()

            threading.Thread(target=read_source, daemon=True).start()
            dialog.after(80, finish_loading)

        def select_group(event: tk.Event) -> None:
            if event.widget is group_tree:
                group_code_combo.set("")

        for combo in mapping_combos.values():
            combo.bind("<<ComboboxSelected>>", lambda _e: refresh_preview())
        sheet_combo.bind("<<ComboboxSelected>>", load_dataset)
        group_tree.bind("<<TreeviewSelect>>", select_group)
        load_dataset()

        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Cancelar", command=dialog.destroy).pack(side="right", padx=(6, 0))

        def commit_import() -> None:
            if dataset is None:
                return
            if not current_preview:
                messagebox.showwarning("Sin filas para importar", "Revise el archivo y las columnas antes de continuar.", parent=dialog)
                return
            source_type = source_labels.get(source_type_combo.get(), "")
            details = summary_label.cget("text")
            if not messagebox.askyesno(
                "Confirmar importación",
                (
                    f"Se guardarán {len(current_preview)} fila(s) del archivo {selected.name}.\n\n{details}\n\n"
                    "Las alertas no se corregirán automáticamente. ¿Desea continuar?"
                ),
                parent=dialog,
            ):
                return
            try:
                result = self.attendance.import_reviewed(
                    dataset,
                    {field: variable.get() for field, variable in mapping_vars.items()},
                    source_type,
                    assignments,
                )
            except (OSError, ValueError, sqlite3.Error) as error:
                messagebox.showerror("No se pudo guardar la importación", str(error), parent=dialog)
                return
            dialog.destroy()
            self._refresh_attendance()
            self._refresh_dashboard_if_visible()
            self._notify(
                f"Importación guardada: {result['imported']} fila(s), {result['invalid']} con alertas y {result['duplicates']} posibles duplicados."
            )

        ttk.Button(buttons, text="Revisar e importar", style="Accent.TButton", command=commit_import).pack(side="right")

    def _export_attendance(self) -> None:
        records = self._attendance_records()
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".csv", filetypes=(("CSV", "*.csv"),))
        if not path:
            return
        try:
            self.attendance.export_csv(Path(path), records)
        except OSError as error:
            messagebox.showerror("No se pudo exportar", str(error), parent=self.root)
            return
        self._notify("Consulta de asistencia exportada correctamente.")


    def _draw_attendance_chart(self, width: int, height: int) -> None:
        if not hasattr(self, "attendance_chart") or not self.attendance_chart.winfo_exists():
            return
        canvas = self.attendance_chart
        canvas.delete("all")
        records = getattr(self, "dashboard_attendance", [])
        total = len(records)
        review = sum(bool(record["alerts"]) for record in records)
        complete = total - review
        center_x = max(width * 0.3, 60)
        center_y = max(height / 2, 50)
        radius = min(height * 0.34, width * 0.2, 50)
        bounds = (
            center_x - radius,
            center_y - radius,
            center_x + radius,
            center_y + radius,
        )
        canvas.create_oval(*bounds, outline="#E9EFF2", width=14)
        if total:
            start = 90
            for value, color in ((complete, TEAL), (review, AMBER)):
                if value:
                    extent = 360 * value / total
                    canvas.create_arc(
                        *bounds,
                        start=start,
                        extent=extent,
                        style="arc",
                        outline=color,
                        width=14,
                    )
                    start -= extent
        canvas.create_text(
            center_x, center_y - 4,
            text=str(total),
            fill=NAVY,
            font=(font_family(), 19, "bold"),
        )
        canvas.create_text(
            center_x, center_y + 17,
            text="registros",
            fill=MUTED,
            font=(font_family(), 8),
        )
        legend_x = center_x + radius + 24
        if legend_x > width - 105:
            legend_x = max(center_x + radius + 12, width * 0.58)
        for index, (label, value, color) in enumerate(
            (("Completas", complete, TEAL), ("Para revisar", review, AMBER))
        ):
            y = center_y - 12 + index * 27
            canvas.create_oval(legend_x, y - 4, legend_x + 8, y + 4, fill=color, outline="")
            canvas.create_text(
                legend_x + 15, y,
                text=f"{label}  {value}",
                anchor="w",
                fill=TEXT,
                font=(font_family(), 8),
            )

    def _draw_weekly_chart(
        self,
        width: int,
        height: int,
        records: list[dict[str, Any]],
    ) -> None:
        if not hasattr(self, "weekly_chart") or not self.weekly_chart.winfo_exists():
            return
        canvas = self.weekly_chart
        canvas.delete("all")
        today = date.today()
        days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
        counts = {day.isoformat(): 0 for day in days}
        for record in records:
            work_date = record.get("work_date", "")
            if work_date in counts:
                counts[work_date] += 1
        left, right, top, bottom = 23, max(width - 12, 24), 12, max(height - 25, 36)
        canvas.create_line(left, bottom, right, bottom, fill=LINE, width=1)
        max_count = max(counts.values(), default=0)
        plot_height = max(bottom - top - 18, 1)
        slot = (right - left) / 7
        bar_width = min(slot * 0.48, 30)
        for index, day in enumerate(days):
            value = counts[day.isoformat()]
            bar_height = (value / max_count * plot_height) if max_count else 0
            center = left + slot * (index + 0.5)
            if value:
                canvas.create_rectangle(
                    center - bar_width / 2,
                    bottom - bar_height,
                    center + bar_width / 2,
                    bottom,
                    fill=TEAL if day == today else "#B8DCD8",
                    outline="",
                )
            canvas.create_text(
                center,
                bottom + 12,
                text=("Hoy" if day == today else f"{day.day:02d}"),
                fill=BLUE if day == today else MUTED,
                font=(font_family(), 7, "bold" if day == today else "normal"),
            )
            if value:
                canvas.create_text(
                    center, bottom - bar_height - 9,
                    text=str(value), fill=MUTED, font=(font_family(), 7),
                )
        if not any(counts.values()):
            canvas.create_text(
                width / 2,
                height / 2,
                text="Sin marcaciones en este periodo",
                fill=MUTED,
                font=(font_family(), 8),
            )

    def _draw_novelty_chart(self, width: int, height: int) -> None:
        if not hasattr(self, "novelty_chart") or not self.novelty_chart.winfo_exists():
            return
        canvas = self.novelty_chart
        canvas.delete("all")
        categories = getattr(self, "dashboard_novelties", ())
        if not any(value for _, value, _ in categories):
            canvas.create_text(
                width / 2,
                height / 2,
                text="Sin novedades registradas",
                fill=MUTED,
                font=(font_family(), 9),
            )
            return
        label_width = min(90, max(width * 0.32, 70))
        value_width = 26
        bar_left = label_width + 7
        bar_right = max(width - value_width - 8, bar_left + 12)
        bar_width = bar_right - bar_left
        row_height = max((height - 12) / max(len(categories), 1), 22)
        top = 7
        maximum = max((value for _, value, _ in categories), default=0)
        for index, (label, value, color) in enumerate(categories):
            y = top + row_height * (index + 0.5)
            canvas.create_text(
                1,
                y,
                text=label,
                anchor="w",
                fill=MUTED,
                font=(font_family(), 7),
            )
            canvas.create_rectangle(
                bar_left,
                y - 4,
                bar_right,
                y + 4,
                fill="#F0F2F7",
                outline="",
            )
            if value and maximum:
                extent = max(bar_width * value / maximum, 4)
                canvas.create_rectangle(
                    bar_left,
                    y - 4,
                    bar_left + extent,
                    y + 4,
                    fill=color,
                    outline="",
                )
            canvas.create_text(
                width - 2,
                y,
                text=str(value),
                anchor="e",
                fill=TEXT,
                font=(font_family(), 8, "bold"),
            )

    @staticmethod
    def _dashboard_recent_activity(
        attendance: list[dict[str, Any]],
        permissions: list[dict[str, Any]],
        overtime: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        for record in attendance:
            status = "Para revisar" if record["alerts"] else "Completa"
            items.append(
                {
                    "created_at": record.get("created_at", ""),
                    "icon": "calendar",
                    "color": AMBER if record["alerts"] else TEAL,
                    "title": f"Asistencia · {record['employee_name']}",
                    "detail": (
                        f"{record['work_date'] or 'Fecha no indicada'} · "
                        f"{record['entry_time'] or '—'}–{record['exit_time'] or '—'} "
                        f"· {status}"
                    ),
                }
            )
        for record in permissions:
            items.append(
                {
                    "created_at": record.get("created_at", ""),
                    "icon": "calendar-check",
                    "color": (
                        GREEN if record["status"] == "Aprobado"
                        else RED if record["status"] == "Rechazado"
                        else AMBER
                    ),
                    "title": f"Permiso · {record['employee_name']}",
                    "detail": (
                        f"{record['start_date']} · {record['permission_type']} "
                        f"· {record['status']}"
                    ),
                }
            )
        for record in overtime:
            items.append(
                {
                    "created_at": record.get("created_at", ""),
                    "icon": "timer",
                    "color": INDIGO,
                    "title": f"Horas extra · {record['employee_name']}",
                    "detail": (
                        f"{record['work_date']} · "
                        f"{record['activity'] or record['shift_type']}"
                    ),
                }
            )
        return sorted(
            items,
            key=lambda item: item["created_at"],
            reverse=True,
        )[:4]

    def _build_employees(self) -> None:
        toolbar = ttk.Frame(self.page_content)
        toolbar.pack(fill="x", pady=(0, 10))
        self.employee_search = tk.StringVar()
        search_frame, search = self._search_bar(
            toolbar, self.employee_search, width=27
        )
        search_frame.pack(side="left", padx=(0, 8))
        search.bind("<KeyRelease>", self._on_employee_search)
        ttk.Button(
            toolbar, text="Buscar por código o nombre", command=self._refresh_employees
        ).pack(side="left", padx=(0, 8))
        IconActionButton(
            toolbar,
            text="Nuevo empleado",
            icon="plus",
            command=self._employee_dialog,
            primary=True,
        ).pack(side="right", padx=(8, 0))
        employee_actions = ttk.Frame(self.page_content)
        employee_actions.pack(fill="x", pady=(0, 8))
        self.employee_actions = employee_actions
        IconActionButton(
            employee_actions,
            text="Eliminar",
            icon="trash",
            command=self._delete_employee,
            danger=True,
        ).pack(side="right", padx=(8, 0))
        ttk.Button(
            employee_actions, text="Activar / desactivar", command=self._toggle_employee
        ).pack(side="right")
        ttk.Button(
            employee_actions, text="Editar seleccionado", command=self._edit_employee
        ).pack(side="right", padx=8)
        self.employee_tree = self._tree(
            self.page_content,
            (
                ("id", "ID", 0),
                ("avatar", "Perfil", 58),
                ("code", "Código interno", 130),
                ("name", "Nombre", 250),
                ("position", "Cargo", 180),
                ("department", "Área", 170),
                ("active", "Estado", 100),
            ),
        )
        self._refresh_employees()

    def _on_employee_search(self, event: tk.Event) -> None:
        if event.widget.winfo_exists():
            self._refresh_employees()

    def _refresh_employees(self) -> None:
        if not hasattr(self, "employee_tree") or not self.employee_tree.winfo_exists():
            return
        self._fill_tree(
            self.employee_tree,
            self.employees.list(self.employee_search.get()),
            lambda record: (
                record["id"],
                self._employee_initials(record["name"]),
                record["code"],
                record["name"],
                record["position"],
                record["department"],
                "Activo" if record["active"] else "Inactivo",
            ),
            lambda record: ("muted",) if not record["active"] else (),
        )

    @staticmethod
    def _employee_initials(name: str) -> str:
        parts = name.strip().split()
        return "".join(part[0] for part in parts[:2]).upper() or "—"

    def _employee_dialog(self, employee: dict[str, Any] | None = None) -> None:
        dialog = self._dialog("Editar empleado" if employee else "Registrar empleado")
        fields = {}
        dialog.columnconfigure(0, weight=1)
        dialog.columnconfigure(1, weight=1)
        for index, (key, label) in enumerate(
            (("code", "Código interno"), ("name", "Nombre"), ("position", "Cargo"), ("department", "Área o departamento"))
        ):
            row, column = divmod(index, 2)
            fields[key] = self._form_entry(
                dialog,
                label,
                row,
                column,
                employee.get(key, "") if employee else "",
            )

        def save() -> None:
            try:
                self.employees.save(
                    fields["code"].get(),
                    fields["name"].get(),
                    fields["position"].get(),
                    fields["department"].get(),
                    employee["id"] if employee else None,
                )
            except (ValueError, sqlite3.Error) as error:
                messagebox.showerror("No se pudo guardar", str(error), parent=dialog)
                return
            dialog.destroy()
            self._refresh_employees()
            self._refresh_comboboxes()
            self._refresh_dashboard_if_visible()
            self._notify(
                "Empleado actualizado." if employee else "Empleado registrado."
            )

        ttk.Button(
            dialog, text="Guardar", style="Accent.TButton", command=save
        ).grid(row=2, column=0, columnspan=2, sticky="e", padx=8, pady=12)

    def _edit_employee(self) -> None:
        record = self._selected_record(self.employee_tree)
        if record:
            self._employee_dialog(self.employees.get(int(record[0])))

    def _toggle_employee(self) -> None:
        record = self._selected_record(self.employee_tree)
        if not record:
            return
        selected = self.employees.get(int(record[0]))
        if not selected:
            return
        action = "desactivar" if selected["active"] else "activar"
        if not messagebox.askyesno(
            "Confirmar acción",
            f"¿Desea {action} a {selected['name']}?",
            parent=self.root,
        ):
            return
        self.employees.set_active(selected["id"], not bool(selected["active"]))
        self._refresh_employees()
        self._refresh_comboboxes()
        self._refresh_dashboard_if_visible()

    def _build_permissions(self) -> None:
        form = ttk.LabelFrame(self.page_content, text="Solicitud de permiso", padding=9)
        form.pack(fill="x")
        self.perm_employee = self._employee_combo(form, "Empleado", 0, 0)
        self.perm_employee_info = ttk.Label(
            self.perm_employee.master,
            text="Nombre, cargo y área se consultan desde la ficha del empleado; no se solicita su número de documento.",
            style="Card.TLabel",
            wraplength=320,
        )
        self.perm_employee_info.pack(anchor="w", fill="x", pady=(4, 0))
        self.perm_employee.bind(
            "<<ComboboxSelected>>", self._update_permission_employee_details
        )
        self.perm_requested = self._form_entry(
            form, "Fecha de registro (interna)", 0, 1, date.today().isoformat()
        )
        self.perm_type = self._form_combo(
            form, "Tipo (F-012)", 0, 2, ("", "Personal", "Cita médica", "Otro")
        )
        self.perm_start_date = self._form_entry(form, "Fecha de inicio", 1, 0, date.today().isoformat())
        self.perm_start_time = self._form_entry(form, "Hora de inicio", 1, 1)
        self.perm_end_date = self._form_entry(form, "Fecha de finalización", 1, 2, date.today().isoformat())
        self.perm_end_time = self._form_entry(form, "Hora de finalización", 2, 0)
        self.perm_duration = self._form_entry(
            form, "Duración reportada (horas)", 2, 1
        )
        self.perm_duration_days = self._form_entry(
            form, "Duración reportada (días)", 2, 2
        )
        self.perm_remunerated = self._form_combo(
            form,
            "Permiso remunerado",
            3,
            0,
            ("", "Remunerado", "No remunerado"),
        )
        self.perm_reason = self._form_entry(form, "Motivo (F-012)", 3, 1)
        self.perm_notes = self._form_entry(form, "Observaciones", 3, 2)
        self.perm_status = self._form_combo(form, "Estado", 4, 0, STATUSES, "Pendiente")
        signature_flags = ttk.Frame(form, style="Card.TFrame")
        signature_flags.grid(row=4, column=1, columnspan=2, padx=6, pady=4, sticky="w")
        self.perm_applicant_signed = tk.BooleanVar(value=False)
        self.perm_manager_approval = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            signature_flags,
            text="Firma solicitante registrada",
            variable=self.perm_applicant_signed,
        ).pack(anchor="w")
        ttk.Checkbutton(
            signature_flags,
            text="Vo. Bo. jefe registrado",
            variable=self.perm_manager_approval,
        ).pack(anchor="w")
        buttons = ttk.Frame(form, style="Card.TFrame")
        buttons.grid(row=5, column=1, columnspan=2, sticky="e", padx=6, pady=5)
        ttk.Button(buttons, text="Nuevo / limpiar", command=self._clear_permission_form).pack(side="left", padx=4)
        ttk.Button(buttons, text="Guardar solicitud", style="Accent.TButton", command=self._save_permission).pack(side="left", padx=4)
        self._update_permission_employee_details()
        ttk.Label(
            self.page_content,
            text="Campos de referencia F-012 v006 (abril de 2024). Las firmas se registran como indicadores; no se almacenan imágenes.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=7)
        permission_actions = ttk.Frame(self.page_content)
        permission_actions.pack(fill="x", pady=(0, 6))
        ttk.Label(
            permission_actions,
            text="Seleccione una solicitud para eliminarla.",
            style="Subtitle.TLabel",
        ).pack(side="left")
        IconActionButton(
            permission_actions,
            text="Eliminar solicitud",
            icon="trash",
            command=self._delete_permission,
            danger=True,
        ).pack(side="right")
        self.permission_tree = self._tree(
            self.page_content,
            (
                ("id", "ID", 0), ("employee_code", "Código", 90),
                ("employee_name", "Empleado", 150), ("requested_on", "Registro interno", 105),
                ("start_date", "Inicio", 90), ("start_time", "Hora", 70),
                ("end_date", "Fin", 90), ("end_time", "Hora", 70),
                ("permission_type", "Tipo", 110), ("reason", "Motivo", 160),
                ("remunerated", "Remunerado", 110),
                ("duration_hours", "Horas", 75), ("duration_days", "Días", 75),
                ("status", "Estado", 95),
                ("applicant_signed", "Firma solicitante", 115),
                ("manager_approval_recorded", "Vo. Bo. jefe", 100),
                ("notes", "Observaciones", 180),
            ),
        )
        self.permission_tree.bind("<<TreeviewSelect>>", self._select_permission)
        self._refresh_permissions()

    def _refresh_permissions(self) -> None:
        if not hasattr(self, "permission_tree") or not self.permission_tree.winfo_exists():
            return
        self._fill_tree(
            self.permission_tree, self.permissions.list(),
            lambda item: (
                item["id"], item["employee_code"], item["employee_name"],
                item["requested_on"], item["start_date"], item["start_time"],
                item["end_date"], item["end_time"], item["permission_type"],
                item["reason"], item["remunerated"],
                item["duration_hours"] or "", item["duration_days"] or "",
                item["status"],
                "Sí" if item["applicant_signed"] else "No",
                "Sí" if item["manager_approval_recorded"] else "No",
                item["notes"],
            ),
            lambda item: (
                "approved" if item["status"] == "Aprobado"
                else "rejected" if item["status"] == "Rechazado"
                else "pending"
            ,),
        )

    def _select_permission(self, event: tk.Event) -> None:
        if event.widget is not self.permission_tree:
            return
        record = self._selected_record(self.permission_tree)
        if not record:
            return
        permission = next(
            (item for item in self.permissions.list() if item["id"] == int(record[0])),
            None,
        )
        if not permission:
            return
        self.editing_permission_id = permission["id"]
        self._set_combo_code(self.perm_employee, permission["employee_code"])
        for widget, key in (
            (self.perm_requested, "requested_on"),
            (self.perm_start_date, "start_date"),
            (self.perm_start_time, "start_time"),
            (self.perm_end_date, "end_date"),
            (self.perm_end_time, "end_time"),
            (self.perm_reason, "reason"),
            (self.perm_notes, "notes"),
            (self.perm_duration, "duration_hours"),
            (self.perm_duration_days, "duration_days"),
        ):
            self._set_entry(widget, str(permission[key]))
        self.perm_type.set(permission["permission_type"])
        self._update_permission_employee_details()
        self.perm_status.set(permission["status"])
        self.perm_remunerated.set(permission["remunerated"])
        self.perm_applicant_signed.set(bool(permission["applicant_signed"]))
        self.perm_manager_approval.set(
            bool(permission["manager_approval_recorded"])
        )

    def _save_permission(self) -> None:
        employee_id = self._combo_id(self.perm_employee)
        if employee_id is None:
            messagebox.showwarning("Falta empleado", "Registre o seleccione un empleado activo.", parent=self.root)
            return
        was_editing = self.editing_permission_id is not None
        try:
            self.permissions.save(
                employee_id, self.perm_requested.get(), self.perm_start_date.get(),
                self.perm_start_time.get(), self.perm_end_date.get(),
                self.perm_end_time.get(), self.perm_type.get(),
                self.perm_notes.get(), self.perm_status.get(),
                self.editing_permission_id,
                remunerated=self.perm_remunerated.get(),
                duration_hours=self.perm_duration.get(),
                duration_days=self.perm_duration_days.get(),
                reason=self.perm_reason.get(),
                applicant_signed=self.perm_applicant_signed.get(),
                manager_approval_recorded=self.perm_manager_approval.get(),
            )
        except (ValueError, sqlite3.Error) as error:
            messagebox.showerror("No se pudo guardar", str(error), parent=self.root)
            return
        self._clear_permission_form()
        self._refresh_permissions()
        self._refresh_dashboard_if_visible()
        self._notify(
            "Permiso actualizado." if was_editing else "Solicitud de permiso guardada."
        )

    def _clear_permission_form(self) -> None:
        self.editing_permission_id = None
        self._set_combo_code(self.perm_employee, "")
        for widget in (
            self.perm_requested, self.perm_start_date, self.perm_start_time,
            self.perm_end_date, self.perm_end_time, self.perm_notes,
            self.perm_reason, self.perm_duration, self.perm_duration_days,
        ):
            widget.delete(0, tk.END)
        self.perm_requested.insert(0, date.today().isoformat())
        self.perm_type.set("")
        self.perm_remunerated.set("")
        self.perm_status.set("Pendiente")
        self.perm_applicant_signed.set(False)
        self.perm_manager_approval.set(False)
        self._update_permission_employee_details()

    def _update_permission_employee_details(
        self, event: tk.Event | None = None
    ) -> None:
        if event is not None and event.widget is not self.perm_employee:
            return
        employee_id = self._combo_id(self.perm_employee)
        employee = self.employees.get(employee_id) if employee_id is not None else None
        if employee is None:
            self.perm_employee_info.configure(
                text=(
                    "Nombre, cargo y área se consultan desde la ficha del empleado; "
                    "no se solicita su número de documento."
                )
            )
            return
        self.perm_employee_info.configure(
            text=(
                f"{employee['name']} · {employee['position'] or 'Cargo no indicado'} "
                f"· {employee['department'] or 'Área no indicada'}"
            )
        )

    def _build_overtime(self) -> None:
        form = ttk.LabelFrame(self.page_content, text="Registro de horas extra", padding=9)
        form.pack(fill="x")
        self.ot_employee = self._employee_combo(form, "Empleado", 0, 0)
        self.ot_date = self._form_entry(form, "Fecha", 0, 1, date.today().isoformat())
        self.ot_period = self._form_entry(form, "Periodo relacionado", 0, 2)
        self.ot_start = self._form_entry(form, "Hora de inicio", 1, 0)
        self.ot_end = self._form_entry(form, "Hora de finalización", 1, 1)
        self.ot_total_hours = self._form_entry(form, "Total de horas reportado", 1, 2)
        self.ot_hours = self._form_entry(form, "Horas extra reportadas", 2, 0)
        self.ot_shift = self._form_combo(form, "Tipo de jornada", 2, 1, SHIFT_TYPES, SHIFT_TYPES[0])
        self.ot_lunch_hour_worked = self._form_combo(
            form,
            "¿Trabajó hora de almuerzo?",
            2,
            2,
            ("No indicado", "Sí", "No"),
            "No indicado",
        )
        self.ot_activity = self._form_entry(form, "Actividad realizada", 3, 0)
        self.ot_authorized_by = self._form_entry(form, "Autorizada por", 3, 1)
        self.ot_approved_by = self._form_entry(form, "Aprobada por", 3, 2)
        self.ot_sunday_holiday = self._form_entry(
            form, "Domingos y festivos (dato F-074)", 4, 0
        )
        self.ot_reported_surcharge = self._form_entry(
            form, "Recargo reportado (no calculado)", 4, 1
        )
        self.ot_authorized = tk.BooleanVar()
        self.ot_notes = self._form_entry(form, "Observaciones", 5, 0)
        ttk.Checkbutton(
            form,
            text="Autorización registrada",
            variable=self.ot_authorized,
        ).grid(row=4, column=2, padx=6, pady=5, sticky="w")
        buttons = ttk.Frame(form, style="Card.TFrame")
        buttons.grid(row=5, column=1, columnspan=2, sticky="e", padx=6, pady=5)
        ttk.Button(buttons, text="Nuevo / limpiar", command=self._clear_overtime_form).pack(side="left", padx=4)
        ttk.Button(buttons, text="Guardar registro", style="Accent.TButton", command=self._save_overtime).pack(side="left", padx=4)
        ttk.Label(
            self.page_content,
            text="La duración se ingresa como dato reportado. La fecha corresponde al día; el periodo, la autorización y la aprobación son informativos. No se liquidan recargos ni valores salariales.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=7)
        overtime_actions = ttk.Frame(self.page_content)
        overtime_actions.pack(fill="x", pady=(0, 6))
        ttk.Label(
            overtime_actions,
            text="Seleccione un registro para eliminarlo.",
            style="Subtitle.TLabel",
        ).pack(side="left")
        IconActionButton(
            overtime_actions,
            text="Eliminar registro",
            icon="trash",
            command=self._delete_overtime,
            danger=True,
        ).pack(side="right")
        self.overtime_tree = self._tree(
            self.page_content,
            (
                ("id", "ID", 0), ("employee_code", "Código", 90),
                ("employee_name", "Empleado", 150), ("work_date", "Día / fecha", 95),
                ("period", "Periodo", 130),
                ("start_time", "Inicio", 80), ("end_time", "Fin", 80),
                ("total_hours", "Total horas", 95),
                ("sunday_holiday", "Domingo / festivo", 120),
                ("reported_surcharge", "Recargo reportado", 140),
                ("hours", "Horas extra", 95), ("shift_type", "Jornada", 150),
                ("lunch_hour_worked", "Hora de almuerzo", 115),
                ("activity", "Actividad", 180), ("authorized", "Autorización", 100),
                ("authorized_by", "Autorizada por", 140),
                ("approved_by", "Aprobada por", 140),
                ("notes", "Observaciones", 170),
            ),
        )
        self.overtime_tree.bind("<<TreeviewSelect>>", self._select_overtime)
        self._refresh_overtime()

    def _refresh_overtime(self) -> None:
        if not hasattr(self, "overtime_tree") or not self.overtime_tree.winfo_exists():
            return
        self._fill_tree(
            self.overtime_tree, self.overtime.list(),
            lambda item: (
                item["id"], item["employee_code"], item["employee_name"],
                item["work_date"], item["period"], item["start_time"],
                item["end_time"], item["total_hours"] or "",
                item["sunday_holiday"], item["reported_surcharge"],
                item["hours"], item["shift_type"],
                (
                    "No indicado"
                    if item["lunch_hour_worked"] is None
                    else "Sí" if item["lunch_hour_worked"] else "No"
                ),
                item["activity"], "Sí" if item["authorized"] else "No",
                item["authorized_by"], item["approved_by"], item["notes"],
            ),
        )

    def _select_overtime(self, event: tk.Event) -> None:
        if event.widget is not self.overtime_tree:
            return
        record = self._selected_record(self.overtime_tree)
        if not record:
            return
        overtime = next(
            (item for item in self.overtime.list() if item["id"] == int(record[0])),
            None,
        )
        if not overtime:
            return
        self.editing_overtime_id = overtime["id"]
        self._set_combo_code(self.ot_employee, overtime["employee_code"])
        for widget, key in (
            (self.ot_date, "work_date"), (self.ot_start, "start_time"),
            (self.ot_end, "end_time"), (self.ot_hours, "hours"),
            (self.ot_total_hours, "total_hours"),
            (self.ot_activity, "activity"), (self.ot_notes, "notes"),
            (self.ot_period, "period"),
            (self.ot_authorized_by, "authorized_by"),
            (self.ot_approved_by, "approved_by"),
            (self.ot_reported_surcharge, "reported_surcharge"),
        ):
            value = overtime[key]
            self._set_entry(widget, "" if value is None else str(value))
        self.ot_shift.set(overtime["shift_type"])
        self.ot_lunch_hour_worked.set(
            "No indicado"
            if overtime["lunch_hour_worked"] is None
            else "Sí" if overtime["lunch_hour_worked"] else "No"
        )
        self._set_entry(self.ot_sunday_holiday, overtime["sunday_holiday"])
        self.ot_authorized.set(bool(overtime["authorized"]))

    def _save_overtime(self) -> None:
        employee_id = self._combo_id(self.ot_employee)
        if employee_id is None:
            messagebox.showwarning("Falta empleado", "Registre o seleccione un empleado activo.", parent=self.root)
            return
        was_editing = self.editing_overtime_id is not None
        try:
            self.overtime.save(
                employee_id, self.ot_date.get(), self.ot_start.get(),
                self.ot_end.get(), self.ot_hours.get(), self.ot_shift.get(),
                self.ot_activity.get(), self.ot_authorized.get(),
                self.ot_notes.get(), self.editing_overtime_id,
                period=self.ot_period.get(),
                authorized_by=self.ot_authorized_by.get(),
                approved_by=self.ot_approved_by.get(),
                total_hours=self.ot_total_hours.get(),
                lunch_hour_worked=(
                    None
                    if self.ot_lunch_hour_worked.get() == "No indicado"
                    else self.ot_lunch_hour_worked.get() == "Sí"
                ),
                sunday_holiday=self.ot_sunday_holiday.get(),
                reported_surcharge=self.ot_reported_surcharge.get(),
            )
        except (ValueError, sqlite3.Error) as error:
            messagebox.showerror("No se pudo guardar", str(error), parent=self.root)
            return
        self._clear_overtime_form()
        self._refresh_overtime()
        self._refresh_dashboard_if_visible()
        self._notify(
            "Registro de horas extra actualizado."
            if was_editing
            else "Registro de horas extra guardado."
        )

    def _clear_overtime_form(self) -> None:
        self.editing_overtime_id = None
        self._set_combo_code(self.ot_employee, "")
        for widget in (
            self.ot_date, self.ot_start, self.ot_end, self.ot_hours,
            self.ot_total_hours, self.ot_sunday_holiday,
            self.ot_activity, self.ot_notes, self.ot_period,
            self.ot_authorized_by, self.ot_approved_by,
            self.ot_reported_surcharge,
        ):
            widget.delete(0, tk.END)
        self.ot_date.insert(0, date.today().isoformat())
        self.ot_shift.set(SHIFT_TYPES[0])
        self.ot_lunch_hour_worked.set("No indicado")
        self.ot_authorized.set(False)

    def _build_reports(self) -> None:
        filters = ttk.LabelFrame(self.page_content, text="Filtros de consulta", padding=8)
        filters.pack(fill="x")
        self.report_type = self._form_combo(
            filters, "Módulo", 0, 0,
            ("Asistencia", "Permisos", "Horas extra", "Empleados"),
            "Asistencia",
        )
        self.report_employee = self._employee_combo(filters, "Empleado", 0, 1, include_all=True)
        self.report_start = self._form_entry(filters, "Desde (AAAA-MM-DD)", 1, 0)
        self.report_end = self._form_entry(filters, "Hasta (AAAA-MM-DD)", 1, 1)
        report_actions = ttk.Frame(filters, style="Card.TFrame")
        report_actions.grid(row=2, column=0, columnspan=2, padx=6, pady=5, sticky="e")
        self.report_actions = report_actions
        ttk.Button(
            report_actions, text="Consultar", style="Accent.TButton",
            command=self._refresh_report,
        ).pack(side="left", padx=(0, 6))
        IconActionButton(
            report_actions,
            text="CSV",
            icon="file-down",
            command=lambda: self._export_report("csv"),
        ).pack(side="left", padx=(0, 6))
        IconActionButton(
            report_actions,
            text="Excel",
            icon="file-down",
            command=lambda: self._export_report("xlsx"),
        ).pack(side="left")
        self.report_hint = ttk.Label(self.page_content, style="Subtitle.TLabel")
        self.report_hint.pack(anchor="w", pady=7)
        report_table = ttk.Frame(self.page_content)
        report_table.pack(fill="both", expand=True)
        report_table.rowconfigure(0, weight=1)
        report_table.columnconfigure(0, weight=1)
        self.report_tree = ttk.Treeview(report_table, show="headings", height=12)
        self.report_tree.grid(row=0, column=0, sticky="nsew")
        self.report_scroll = ttk.Scrollbar(
            report_table, orient="vertical", command=self.report_tree.yview
        )
        self.report_scroll.grid(row=0, column=1, sticky="ns")
        report_horizontal = ttk.Scrollbar(
            report_table, orient="horizontal", command=self.report_tree.xview
        )
        report_horizontal.grid(row=1, column=0, sticky="ew")
        self.report_tree.configure(
            yscrollcommand=self.report_scroll.set,
            xscrollcommand=report_horizontal.set,
        )
        self._bind_table_scroll(self.report_tree)
        self.report_tree.tag_configure("even", background=WHITE)
        self.report_tree.tag_configure("odd", background="#F7FAFC")
        self.report_empty_label = tk.Label(
            report_table,
            text="No hay resultados para los filtros seleccionados.",
            background=WHITE,
            foreground=MUTED,
            font=(font_family(), 9),
        )
        self.report_records: list[dict[str, Any]] = []
        self.report_columns: list[str] = []
        self.report_type.bind("<<ComboboxSelected>>", self._on_report_type_changed)
        self._refresh_report()

    def _on_report_type_changed(self, event: tk.Event) -> None:
        if event.widget is self.report_type:
            self._refresh_report()

    def _refresh_report(self) -> None:
        if not hasattr(self, "report_tree") or not self.report_tree.winfo_exists():
            return
        kind = self.report_type.get()
        employee_id = self._combo_id(self.report_employee)
        start, end = self.report_start.get().strip(), self.report_end.get().strip()
        try:
            self.attendance.validate_period(start, end)
        except ValueError as error:
            messagebox.showwarning("Revise el periodo", str(error), parent=self.root)
            return
        if kind == "Asistencia":
            records = self.attendance.list(employee_id, start, end)
            columns = [
                "employee_code", "employee_name", "work_date", "entry_time",
                "exit_time", "source", "alerts",
            ]
            headers = [
                "Código", "Empleado", "Fecha", "Entrada", "Salida",
                "Fuente", "Observaciones",
            ]
            for record in records:
                record["alerts"] = "; ".join(record["alerts"])
        elif kind == "Permisos":
            records = self.permissions.list(employee_id, start, end)
            columns = [
                "employee_code", "employee_name", "requested_on", "start_date",
                "start_time", "end_date", "end_time", "permission_type", "reason",
                "remunerated", "duration_hours", "duration_days", "status",
                "applicant_signed", "manager_approval_recorded", "notes",
            ]
            headers = [
                "Código", "Empleado", "Registro interno", "Inicio", "Hora inicio",
                "Fin", "Hora fin", "Tipo", "Motivo", "Remunerado", "Horas",
                "Días", "Estado", "Firma solicitante", "Vo. Bo. jefe",
                "Observaciones",
            ]
            for record in records:
                record["applicant_signed"] = (
                    "Sí" if record["applicant_signed"] else "No"
                )
                record["manager_approval_recorded"] = (
                    "Sí" if record["manager_approval_recorded"] else "No"
                )
        elif kind == "Horas extra":
            records = self.overtime.list(employee_id, start, end)
            columns = [
                "employee_code", "employee_name", "period", "work_date",
                "start_time", "end_time", "total_hours", "hours",
                "sunday_holiday", "reported_surcharge", "shift_type",
                "activity", "lunch_hour_worked", "authorized", "authorized_by",
                "approved_by", "notes",
            ]
            headers = [
                "Código", "Empleado", "Periodo", "Fecha/día", "Inicio", "Fin",
                "Total horas reportado", "Horas extra reportadas",
                "Domingos y festivos", "Recargo reportado (no calculado)",
                "Jornada", "Actividad", "Hora de almuerzo trabajada",
                "Autorización registrada", "Autorizada por", "Aprobada por",
                "Observaciones",
            ]
            for record in records:
                record["authorized"] = "Sí" if record["authorized"] else "No"
                record["lunch_hour_worked"] = (
                    "No indicado"
                    if record["lunch_hour_worked"] is None
                    else "Sí" if record["lunch_hour_worked"] else "No"
                )
        else:
            records = self.employees.list()
            if employee_id is not None:
                records = [item for item in records if item["id"] == employee_id]
            columns = ["code", "name", "position", "department", "active"]
            headers = ["Código", "Nombre", "Cargo", "Área", "Estado"]
            for record in records:
                record["active"] = "Activo" if record["active"] else "Inactivo"

        self.report_records = records
        self.report_columns = columns
        self.report_headers = headers
        self.report_tree.configure(
            columns=tuple(f"c{index}" for index in range(len(headers)))
        )
        for index, header in enumerate(headers):
            column = f"c{index}"
            self.report_tree.heading(column, text=header)
            self.report_tree.column(column, width=145, minwidth=85, anchor="w")
        self.report_tree.delete(*self.report_tree.get_children())
        for index, record in enumerate(records):
            self.report_tree.insert(
                "", "end",
                values=tuple(str(record.get(column, "")) for column in columns),
                tags=("even" if index % 2 == 0 else "odd",),
            )
        if records:
            self.report_empty_label.place_forget()
        else:
            self.report_empty_label.place(relx=0.5, rely=0.5, anchor="center")
        self.report_hint.configure(text=f"{len(records)} registro(s) | {kind}")

    def _export_report(self, format_name: str) -> None:
        records = self.report_records
        if not records:
            messagebox.showinfo("Sin resultados", "No hay registros para exportar.", parent=self.root)
            return
        extension = ".xlsx" if format_name == "xlsx" else ".csv"
        path = filedialog.asksaveasfilename(
            parent=self.root, defaultextension=extension,
            filetypes=(("Excel", "*.xlsx"),) if extension == ".xlsx" else (("CSV", "*.csv"),),
        )
        if not path:
            return
        try:
            if format_name == "xlsx":
                fields, headers = self.report_export_columns
                export_records = [
                    {
                        header: record.get(field, "")
                        for field, header in zip(fields, headers)
                    }
                    for record in records
                ]
                self.reports.export_excel(
                    Path(path), export_records, headers
                )
            else:
                fields, headers = self.report_export_columns
                export_records = [
                    {
                        header: record.get(field, "")
                        for field, header in zip(fields, headers)
                    }
                    for record in records
                ]
                self.reports.export_csv(Path(path), export_records, headers)
        except (OSError, RuntimeError, ValueError) as error:
            messagebox.showerror("No se pudo exportar", str(error), parent=self.root)
            return
        self._notify(f"Informe {extension[1:].upper()} exportado correctamente.")

    @property
    def report_export_columns(self) -> tuple[list[str], list[str]]:
        kind = self.report_type.get()
        return {
            "Asistencia": (
                ["employee_code", "work_date", "entry_time", "exit_time", "alerts"],
                ["Código", "Fecha", "Entrada", "Salida", "Observaciones"],
            ),
            "Permisos": (
                [
                    "employee_code", "requested_on", "start_date", "start_time",
                    "end_date", "end_time", "permission_type", "remunerated",
                    "duration_hours", "duration_days", "status", "applicant_signed",
                    "manager_approval_recorded",
                ],
                [
                    "Código", "Registro interno", "Inicio", "Hora inicio", "Fin",
                    "Hora fin", "Tipo", "Remunerado", "Horas", "Días", "Estado",
                    "Firma solicitante registrada", "Vo. Bo. jefe registrado",
                ],
            ),
            "Horas extra": (
                [
                    "employee_code", "work_date", "start_time", "end_time",
                    "total_hours", "hours", "shift_type", "lunch_hour_worked",
                    "authorized",
                ],
                [
                    "Código", "Fecha/día", "Inicio", "Fin", "Total horas reportado",
                    "Horas extra reportadas", "Jornada", "Hora de almuerzo trabajada",
                    "Autorización registrada",
                ],
            ),
            "Empleados": (["code", "active"], ["Código", "Estado"]),
        }[kind]

    def _refresh_dashboard_if_visible(self) -> None:
        if self.current_page == "Panel principal":
            self.show_page("Panel principal")

    def _delete_employee(self) -> None:
        selected = self._selected_record(self.employee_tree)
        if not selected:
            return
        employee_id = int(selected[0])
        employee = self.employees.get(employee_id)
        if employee is None:
            messagebox.showwarning(
                "Registro no disponible",
                "El empleado seleccionado ya no existe.",
                parent=self.root,
            )
            self._refresh_employees()
            return
        if not messagebox.askyesno(
            "Eliminar empleado",
            f"¿Eliminar a {employee['name']}? Solo se permite si no conserva historial asociado.",
            parent=self.root,
        ):
            return
        try:
            self.employees.delete(employee_id)
        except ValueError as error:
            messagebox.showwarning(
                "No se puede eliminar el empleado", str(error), parent=self.root
            )
            return
        except sqlite3.Error as error:
            messagebox.showerror(
                "No se pudo eliminar el empleado", str(error), parent=self.root
            )
            return
        self._refresh_employees()
        self._refresh_comboboxes()
        self._refresh_dashboard_if_visible()
        self._notify("Empleado eliminado.")

    def _delete_permission(self) -> None:
        selected = self._selected_record(self.permission_tree)
        if not selected:
            return
        permission_id = int(selected[0])
        permission = next(
            (item for item in self.permissions.list() if item["id"] == permission_id),
            None,
        )
        if permission is None:
            messagebox.showwarning(
                "Registro no disponible",
                "La solicitud seleccionada ya no existe.",
                parent=self.root,
            )
            self._refresh_permissions()
            return
        if not messagebox.askyesno(
            "Eliminar solicitud",
            f"¿Eliminar la solicitud de {permission['employee_name']}? Esta acción no se puede deshacer.",
            parent=self.root,
        ):
            return
        try:
            self.permissions.delete(permission_id)
        except (ValueError, sqlite3.Error) as error:
            messagebox.showerror(
                "No se pudo eliminar la solicitud", str(error), parent=self.root
            )
            return
        if self.editing_permission_id == permission_id:
            self._clear_permission_form()
        self._refresh_permissions()
        self._refresh_dashboard_if_visible()
        self._notify("Solicitud eliminada.")

    def _delete_overtime(self) -> None:
        selected = self._selected_record(self.overtime_tree)
        if not selected:
            return
        overtime_id = int(selected[0])
        overtime = next(
            (item for item in self.overtime.list() if item["id"] == overtime_id),
            None,
        )
        if overtime is None:
            messagebox.showwarning(
                "Registro no disponible",
                "El registro seleccionado ya no existe.",
                parent=self.root,
            )
            self._refresh_overtime()
            return
        if not messagebox.askyesno(
            "Eliminar horas extra",
            f"¿Eliminar el registro de {overtime['employee_name']} del {overtime['work_date']}? Esta acción no se puede deshacer.",
            parent=self.root,
        ):
            return
        try:
            self.overtime.delete(overtime_id)
        except (ValueError, sqlite3.Error) as error:
            messagebox.showerror(
                "No se pudo eliminar el registro", str(error), parent=self.root
            )
            return
        if self.editing_overtime_id == overtime_id:
            self._clear_overtime_form()
        self._refresh_overtime()
        self._refresh_dashboard_if_visible()
        self._notify("Registro de horas extra eliminado.")

    def _refresh_comboboxes(self) -> None:
        employees = self.employees.list(include_inactive=False)
        for name in (
            "att_employee", "att_filter_employee", "perm_employee",
            "ot_employee", "report_employee",
        ):
            combo = getattr(self, name, None)
            if combo is None or not combo.winfo_exists():
                continue
            current = self._combo_code(combo)
            prefix = ["Todos"] if getattr(combo, "_include_all", False) else [""]
            labels = {
                self._employee_option(item): item["code"] for item in employees
            }
            combo._employee_code_by_label = labels
            combo.configure(values=prefix + list(labels), height=10)
            selected = next(
                (label for label, code in labels.items() if code == current), None
            )
            combo.set(selected if selected is not None else prefix[0])
        permission_combo = getattr(self, "perm_employee", None)
        permission_info = getattr(self, "perm_employee_info", None)
        if (
            permission_combo is not None
            and permission_info is not None
            and permission_combo.winfo_exists()
            and permission_info.winfo_exists()
        ):
            self._update_permission_employee_details()

    def _search_bar(
        self,
        parent: tk.Misc,
        variable: tk.StringVar,
        width: int = 28,
    ) -> tuple[tk.Frame, ttk.Entry]:
        frame = tk.Frame(
            parent,
            background=WHITE,
            highlightbackground=LINE,
            highlightthickness=1,
        )
        icon = create_icon_canvas(frame, "search", MUTED, WHITE, size=17)
        icon.pack(side="left", padx=(9, 5), pady=5)
        entry = ttk.Entry(frame, textvariable=variable, width=width)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 9), pady=2)
        return frame, entry

    def _employee_combo(
        self,
        parent: ttk.Frame,
        label: str,
        row: int,
        column: int,
        include_all: bool = False,
    ) -> ttk.Combobox:
        employees = self.employees.list(include_inactive=False)
        labels = {
            self._employee_option(item): item["code"] for item in employees
        }
        prefix = ["Todos"] if include_all else [""]
        combo = self._form_combo(
            parent, label, row, column, prefix + list(labels),
            prefix[0],
        )
        combo._include_all = include_all  # type: ignore[attr-defined]
        combo._employee_code_by_label = labels  # type: ignore[attr-defined]
        combo.configure(height=10)
        combo.configure(state="readonly")
        return combo

    def _combo_id(self, combo: ttk.Combobox) -> int | None:
        code = self._combo_code(combo)
        if not code:
            return None
        employee = self.database.fetch_one(
            """
            SELECT id FROM employees
            WHERE code = ? COLLATE NOCASE AND active = 1
            """,
            (code,),
        )
        return int(employee["id"]) if employee else None

    @staticmethod
    def _combo_code(combo: ttk.Combobox) -> str:
        value = combo.get().strip()
        if value == "Todos":
            return ""
        return getattr(combo, "_employee_code_by_label", {}).get(value, value)

    @staticmethod
    def _set_combo_code(combo: ttk.Combobox, code: str) -> None:
        labels = getattr(combo, "_employee_code_by_label", {})
        label = next((name for name, value in labels.items() if value == code), code)
        combo.set(label)

    @staticmethod
    def _employee_option(employee: dict[str, Any]) -> str:
        return f"{employee['code']} | {employee['name']}"

    def _form_entry(
        self, parent: ttk.Frame, label: str, row: int, column: int, value: str = ""
    ) -> ttk.Entry:
        cell = ttk.Frame(parent, style="Card.TFrame")
        cell.grid(row=row, column=column, padx=6, pady=4, sticky="ew")
        parent.columnconfigure(column, weight=1)
        ttk.Label(cell, text=label, style="Card.TLabel").pack(anchor="w")
        entry = ttk.Entry(cell, width=24)
        entry.pack(fill="x", pady=(2, 0))
        if value:
            entry.insert(0, value)
        return entry

    def _form_combo(
        self,
        parent: ttk.Frame,
        label: str,
        row: int,
        column: int,
        values: tuple[str, ...] | list[str],
        selected: str = "",
    ) -> ttk.Combobox:
        cell = ttk.Frame(parent, style="Card.TFrame")
        cell.grid(row=row, column=column, padx=6, pady=4, sticky="ew")
        parent.columnconfigure(column, weight=1)
        ttk.Label(cell, text=label, style="Card.TLabel").pack(anchor="w")
        combo = ttk.Combobox(cell, values=values, width=22)
        combo.pack(fill="x", pady=(2, 0))
        if selected:
            combo.set(selected)
        return combo

    def _dialog(self, title: str) -> tk.Toplevel:
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.after(10, lambda: self._center_dialog(dialog))
        return dialog

    def _center_dialog(self, dialog: tk.Toplevel) -> None:
        if not dialog.winfo_exists():
            return
        self.root.update_idletasks()
        dialog.update_idletasks()
        x = self.root.winfo_rootx() + (
            self.root.winfo_width() - dialog.winfo_width()
        ) // 2
        y = self.root.winfo_rooty() + (
            self.root.winfo_height() - dialog.winfo_height()
        ) // 2
        dialog.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    @staticmethod
    def _set_entry(entry: ttk.Entry, value: str) -> None:
        entry.delete(0, tk.END)
        entry.insert(0, value)

    def _tree(
        self,
        parent: ttk.Frame,
        columns: tuple[tuple[str, str, int], ...],
    ) -> ttk.Treeview:
        container = ttk.Frame(parent, style="Card.TFrame")
        container.pack(fill="both", expand=True)
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        visible_columns = tuple(
            column[0] for column in columns if column[2] > 0
        )
        tree = ttk.Treeview(
            container,
            columns=tuple(column[0] for column in columns),
            displaycolumns=visible_columns,
            show="headings",
            selectmode="browse",
            height=12,
        )
        for key, label, width in columns:
            tree.heading(key, text=label)
            tree.column(
                key,
                width=max(width, 1),
                minwidth=max(min(width, 70), 1),
                anchor="w",
                stretch=width > 250,
            )
        tree.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(
            container, orient="vertical", command=tree.yview
        )
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(
            container, orient="horizontal", command=tree.xview
        )
        horizontal.grid(row=1, column=0, sticky="ew")
        tree.configure(
            yscrollcommand=vertical.set,
            xscrollcommand=horizontal.set,
        )
        self._bind_table_scroll(tree)
        tree.tag_configure("even", background=WHITE)
        tree.tag_configure("odd", background="#F7FAFC")
        tree.tag_configure("warning", foreground=AMBER, background="#FFFAF1")
        tree.tag_configure("muted", foreground=MUTED)
        tree.tag_configure("approved", foreground=GREEN)
        tree.tag_configure("rejected", foreground=RED)
        tree.tag_configure("pending", foreground=AMBER)
        empty_label = tk.Label(
            container,
            text="No hay registros para mostrar.",
            background=WHITE,
            foreground=MUTED,
            font=(font_family(), 9),
        )
        empty_label.place(relx=0.5, rely=0.48, anchor="center")
        tree._empty_label = empty_label
        return tree

    @staticmethod
    def _fill_tree(
        tree: ttk.Treeview,
        records: list[dict[str, Any]],
        values: Callable[[dict[str, Any]], tuple[Any, ...]],
        tags: Callable[[dict[str, Any]], tuple[str, ...]] | None = None,
    ) -> None:
        tree.delete(*tree.get_children())
        empty_label = getattr(tree, "_empty_label", None)
        if empty_label is not None:
            if records:
                empty_label.place_forget()
            else:
                empty_label.place(relx=0.5, rely=0.48, anchor="center")
        for index, record in enumerate(records):
            row_tags = ["even" if index % 2 == 0 else "odd"]
            if tags:
                row_tags.extend(tags(record))
            tree.insert(
                "", "end", values=values(record),
                tags=tuple(row_tags),
            )

    @staticmethod
    def _selected_record(tree: ttk.Treeview) -> tuple[str, ...] | None:
        selected = tree.selection()
        if not selected:
            messagebox.showinfo("Seleccione un registro", "Seleccione primero una fila de la tabla.", parent=tree)
            return None
        return tuple(str(value) for value in tree.item(selected[0], "values"))

    def _notify(self, text: str, kind: str = "success") -> None:
        self._refresh_notification_badge(refresh=True)
        colors = {
            "success": (GREEN, GREEN_PALE),
            "warning": (AMBER, AMBER_PALE),
            "error": (RED, RED_PALE),
        }
        foreground, background = colors.get(kind, colors["success"])
        if self._toast_after_id is not None:
            self.root.after_cancel(self._toast_after_id)
        self.toast.configure(
            text=text,
            foreground=foreground,
            background=background,
        )
        self.toast.place(relx=1.0, x=-4, rely=1.0, y=-8, anchor="se")
        self.toast.lift()
        self._toast_after_id = self.root.after(2800, self.toast.place_forget)

    def close(self) -> None:
        for callback_id in self.root.tk.call("after", "info"):
            self.root.after_cancel(callback_id)
        self._toast_after_id = None
        self.database.close()
        self.root.destroy()
