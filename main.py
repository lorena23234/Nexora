from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path

from database import Database
from views.ventana_principal import MainWindow

DATABASE_PATH = Path(__file__).resolve().parent / "data" / "asistencia_laboral.db"


def _database_path() -> Path | str:
    configured_path = os.environ.get("NEXORA_HR_DB_PATH", "").strip()
    if not configured_path:
        return DATABASE_PATH
    if configured_path == ":memory:":
        return configured_path
    return Path(configured_path).expanduser()


def main() -> None:
    root = tk.Tk()
    database = Database(_database_path())
    MainWindow(root, database)
    root.mainloop()


if __name__ == "__main__":
    main()
