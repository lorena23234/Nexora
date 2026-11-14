from __future__ import annotations

import sqlite3
from typing import Any

from database import Database


class EmployeeService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def list(self, query: str = "", include_inactive: bool = True) -> list[dict[str, Any]]:
        conditions: list[str] = []
        parameters: list[Any] = []
        if not include_inactive:
            conditions.append("active = 1")
        if query.strip():
            like = f"%{query.strip()}%"
            conditions.append("(code LIKE ? OR name LIKE ?)")
            parameters.extend((like, like))
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return self.database.fetch_all(
            f"""
            SELECT id, code, name, position, department, active
            FROM employees {where}
            ORDER BY active DESC, name COLLATE NOCASE
            """,
            tuple(parameters),
        )

    def get(self, employee_id: int) -> dict[str, Any] | None:
        return self.database.fetch_one(
            "SELECT id, code, name, position, department, active "
            "FROM employees WHERE id = ?",
            (employee_id,),
        )

    def save(
        self,
        code: str,
        name: str,
        position: str = "",
        department: str = "",
        employee_id: int | None = None,
    ) -> int:
        code, name = code.strip(), name.strip()
        if not code or not name:
            raise ValueError("El código interno y el nombre son obligatorios.")
        try:
            if employee_id is None:
                cursor = self.database.execute(
                    """
                    INSERT INTO employees (code, name, position, department)
                    VALUES (?, ?, ?, ?)
                    """,
                    (code, name, position.strip(), department.strip()),
                )
                return int(cursor.lastrowid)
            self.database.execute(
                """
                UPDATE employees
                SET code = ?, name = ?, position = ?, department = ?
                WHERE id = ?
                """,
                (code, name, position.strip(), department.strip(), employee_id),
            )
            return employee_id
        except sqlite3.IntegrityError as error:
            if "employees.code" in str(error):
                raise ValueError("Ya existe un empleado con ese código.") from error
            raise

    def set_active(self, employee_id: int, active: bool) -> None:
        self.database.execute(
            "UPDATE employees SET active = ? WHERE id = ?",
            (int(active), employee_id),
        )

    def delete(self, employee_id: int) -> None:
        with self.database.connection:
            employee = self.database.connection.execute(
                "SELECT id FROM employees WHERE id = ?",
                (employee_id,),
            ).fetchone()
            if employee is None:
                raise ValueError("El empleado seleccionado ya no existe.")

            references = {
                table: int(
                    self.database.connection.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE employee_id = ?",
                        (employee_id,),
                    ).fetchone()[0]
                )
                for table in ("attendance", "permissions", "overtime")
            }
            if any(references.values()):
                related = ", ".join(
                    f"{count} {label}"
                    for table, count, label in (
                        ("attendance", references["attendance"], "marcación(es)"),
                        ("permissions", references["permissions"], "permiso(s)"),
                        ("overtime", references["overtime"], "registro(s) de horas extra"),
                    )
                    if count
                )
                raise ValueError(
                    "No se puede eliminar este empleado porque conserva "
                    f"historial asociado: {related}. Desactívelo para conservar "
                    "la trazabilidad."
                )

            self.database.connection.execute(
                "DELETE FROM employees WHERE id = ?",
                (employee_id,),
            )
