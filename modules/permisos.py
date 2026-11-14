from __future__ import annotations

from datetime import datetime
import math
from typing import Any

from database import Database
from modules.validaciones import valid_date, valid_time

STATUSES = ("Pendiente", "Aprobado", "Rechazado")


class PermissionService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def list(
        self,
        employee_id: int | None = None,
        start_date: str = "",
        end_date: str = "",
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        parameters: list[Any] = []
        if employee_id is not None:
            conditions.append("p.employee_id = ?")
            parameters.append(employee_id)
        if start_date:
            conditions.append("p.end_date >= ?")
            parameters.append(start_date)
        if end_date:
            conditions.append("p.start_date <= ?")
            parameters.append(end_date)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return self.database.fetch_all(
            f"""
            SELECT p.*, e.code AS employee_code, e.name AS employee_name
            FROM permissions p JOIN employees e ON e.id = p.employee_id
            {where}
            ORDER BY p.start_date DESC, p.id DESC
            """,
            tuple(parameters),
        )

    def save(
        self,
        employee_id: int,
        requested_on: str,
        start_date: str,
        start_time: str,
        end_date: str,
        end_time: str,
        permission_type: str,
        notes: str = "",
        status: str = "Pendiente",
        permission_id: int | None = None,
        remunerated: str = "",
        duration_hours: str | float | None = None,
        applicant_signed: bool = False,
        manager_approval_recorded: bool = False,
        duration_days: str | float | None = None,
        reason: str = "",
    ) -> int:
        if status not in STATUSES:
            raise ValueError("Seleccione un estado válido.")
        if remunerated not in ("", "Remunerado", "No remunerado"):
            raise ValueError("Seleccione una clasificación de permiso válida.")
        if not permission_type.strip():
            raise ValueError("Indique el tipo o motivo del permiso.")
        for label, value in (
            ("solicitud", requested_on),
            ("inicio", start_date),
            ("fin", end_date),
        ):
            if not valid_date(value.strip()):
                raise ValueError(f"La fecha de {label} debe tener formato AAAA-MM-DD.")
        for label, value in (("inicio", start_time), ("fin", end_time)):
            if not valid_time(value.strip()):
                raise ValueError(f"La hora de {label} debe tener formato HH:MM.")
        start = datetime.fromisoformat(
            f"{start_date.strip()}T{start_time.strip()}"
        )
        end = datetime.fromisoformat(f"{end_date.strip()}T{end_time.strip()}")
        if end <= start:
            raise ValueError("La finalización debe ser posterior al inicio.")
        duration_value: float | None = None
        if duration_hours not in (None, ""):
            try:
                duration_value = float(duration_hours)
            except (ValueError, TypeError) as error:
                raise ValueError("La duración reportada debe ser numérica.") from error
            if not math.isfinite(duration_value) or not 0 < duration_value <= 24:
                raise ValueError("La duración reportada debe ser mayor que 0 y hasta 24 horas.")
        duration_days_value: float | None = None
        if duration_days not in (None, ""):
            try:
                duration_days_value = float(duration_days)
            except (ValueError, TypeError) as error:
                raise ValueError(
                    "La duración reportada en días debe ser numérica."
                ) from error
            if not math.isfinite(duration_days_value) or duration_days_value <= 0:
                raise ValueError(
                    "La duración reportada en días debe ser mayor que 0."
                )

        values = (
            employee_id,
            requested_on.strip(),
            start_date.strip(),
            start_time.strip(),
            end_date.strip(),
            end_time.strip(),
            permission_type.strip(),
            notes.strip(),
            reason.strip(),
            status,
            remunerated,
            duration_value,
            duration_days_value,
            int(applicant_signed),
            int(manager_approval_recorded),
        )
        if permission_id is None:
            cursor = self.database.execute(
                """
                INSERT INTO permissions (
                    employee_id, requested_on, start_date, start_time,
                    end_date, end_time, permission_type, notes, reason, status,
                    remunerated, duration_hours, duration_days, applicant_signed,
                    manager_approval_recorded
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            return int(cursor.lastrowid)
        self.database.execute(
            """
            UPDATE permissions SET employee_id = ?, requested_on = ?,
                start_date = ?, start_time = ?, end_date = ?, end_time = ?,
                permission_type = ?, notes = ?, reason = ?, status = ?,
                remunerated = ?, duration_hours = ?, duration_days = ?, applicant_signed = ?,
                manager_approval_recorded = ?
            WHERE id = ?
            """,
            (*values, permission_id),
        )
        return permission_id

    def delete(self, permission_id: int) -> None:
        cursor = self.database.execute(
            "DELETE FROM permissions WHERE id = ?",
            (permission_id,),
        )
        if cursor.rowcount == 0:
            raise ValueError("La solicitud de permiso seleccionada ya no existe.")
