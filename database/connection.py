from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    position TEXT NOT NULL DEFAULT '',
    department TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY,
    employee_id INTEGER REFERENCES employees(id) ON DELETE RESTRICT,
    employee_code TEXT NOT NULL DEFAULT '',
    work_date TEXT NOT NULL DEFAULT '',
    entry_time TEXT NOT NULL DEFAULT '',
    exit_time TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    import_batch_id INTEGER REFERENCES attendance_imports(id) ON DELETE SET NULL,
    source_row INTEGER,
    raw_data TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS attendance_imports (
    id INTEGER PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (
        source_type IN (
            'original_verificado',
            'transcripcion_documental',
            'datos_sinteticos',
            'no_verificada'
        )
    ),
    mapping_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS permissions (
    id INTEGER PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE RESTRICT,
    requested_on TEXT NOT NULL,
    start_date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_date TEXT NOT NULL,
    end_time TEXT NOT NULL,
    permission_type TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Pendiente'
        CHECK (status IN ('Pendiente', 'Aprobado', 'Rechazado')),
    remunerated TEXT NOT NULL DEFAULT ''
        CHECK (remunerated IN ('', 'Remunerado', 'No remunerado')),
    duration_hours REAL CHECK (
        duration_hours IS NULL OR (duration_hours > 0 AND duration_hours <= 24)
    ),
    duration_days REAL CHECK (
        duration_days IS NULL OR duration_days > 0
    ),
    applicant_signed INTEGER NOT NULL DEFAULT 0 CHECK (applicant_signed IN (0, 1)),
    manager_approval_recorded INTEGER NOT NULL DEFAULT 0
        CHECK (manager_approval_recorded IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS overtime (
    id INTEGER PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE RESTRICT,
    work_date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    hours REAL NOT NULL CHECK (hours > 0 AND hours <= 24),
    shift_type TEXT NOT NULL,
    activity TEXT NOT NULL DEFAULT '',
    authorized INTEGER NOT NULL DEFAULT 0 CHECK (authorized IN (0, 1)),
    period TEXT NOT NULL DEFAULT '',
    authorized_by TEXT NOT NULL DEFAULT '',
    approved_by TEXT NOT NULL DEFAULT '',
    total_hours REAL CHECK (
        total_hours IS NULL OR (total_hours > 0 AND total_hours <= 24)
    ),
    reported_surcharge TEXT NOT NULL DEFAULT '',
    sunday_holiday TEXT NOT NULL DEFAULT '',
    lunch_hour_worked INTEGER CHECK (
        lunch_hour_worked IS NULL OR lunch_hour_worked IN (0, 1)
    ),
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(work_date);
CREATE INDEX IF NOT EXISTS idx_attendance_employee ON attendance(employee_id);
CREATE INDEX IF NOT EXISTS idx_permissions_employee ON permissions(employee_id);
CREATE INDEX IF NOT EXISTS idx_permissions_dates ON permissions(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_overtime_employee ON overtime(employee_id);
CREATE INDEX IF NOT EXISTS idx_overtime_date ON overtime(work_date);
"""


class Database:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path))
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(SCHEMA)
        self._migrate()
        self.connection.commit()

    def _migrate(self) -> None:
        migrations = {
            "attendance": {
                "import_batch_id": "INTEGER REFERENCES attendance_imports(id) ON DELETE SET NULL",
                "source_row": "INTEGER",
                "raw_data": "TEXT NOT NULL DEFAULT ''",
            },
            "permissions": {
                "remunerated": "TEXT NOT NULL DEFAULT ''",
                "duration_hours": "REAL",
                "duration_days": "REAL",
                "reason": "TEXT NOT NULL DEFAULT ''",
                "applicant_signed": "INTEGER NOT NULL DEFAULT 0",
                "manager_approval_recorded": "INTEGER NOT NULL DEFAULT 0",
            },
            "overtime": {
                "period": "TEXT NOT NULL DEFAULT ''",
                "authorized_by": "TEXT NOT NULL DEFAULT ''",
                "approved_by": "TEXT NOT NULL DEFAULT ''",
                "total_hours": "REAL",
                "reported_surcharge": "TEXT NOT NULL DEFAULT ''",
                "sunday_holiday": "TEXT NOT NULL DEFAULT ''",
                "lunch_hour_worked": "INTEGER",
            },
        }
        for table, columns in migrations.items():
            existing = {
                row["name"]
                for row in self.connection.execute(
                    f"PRAGMA table_info({table})"
                ).fetchall()
            }
            for name, definition in columns.items():
                if name not in existing:
                    self.connection.execute(
                        f"ALTER TABLE {table} ADD COLUMN {name} {definition}"
                    )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_attendance_batch "
            "ON attendance(import_batch_id)"
        )

    def execute(
        self, sql: str, parameters: tuple[Any, ...] = ()
    ) -> sqlite3.Cursor:
        cursor = self.connection.execute(sql, parameters)
        self.connection.commit()
        return cursor

    def execute_many(
        self, sql: str, parameters: list[tuple[Any, ...]]
    ) -> int:
        with self.connection:
            cursor = self.connection.executemany(sql, parameters)
        return cursor.rowcount

    def fetch_all(
        self, sql: str, parameters: tuple[Any, ...] = ()
    ) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in self.connection.execute(sql, parameters).fetchall()
        ]

    def fetch_one(
        self, sql: str, parameters: tuple[Any, ...] = ()
    ) -> dict[str, Any] | None:
        row = self.connection.execute(sql, parameters).fetchone()
        return dict(row) if row is not None else None

    def close(self) -> None:
        self.connection.close()
