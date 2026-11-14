from __future__ import annotations

from datetime import datetime
from typing import Any

from database import Database
from modules.validaciones import valid_date, valid_time

SHIFT_TYPES = ("Diurna", "Nocturna", "Dominical o festiva", "Otra")


class OvertimeService:
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
            conditions.append("o.employee_id = ?")
            parameters.append(employee_id)
        if start_date:
            conditions.append("o.work_date >= ?")
            parameters.append(start_date)
        if end_date:
            conditions.append("o.work_date <= ?")
            parameters.append(end_date)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return self.database.fetch_all(
            f"""
            SELECT o.*, e.code AS employee_code, e.name AS employee_name
            FROM overtime o JOIN employees e ON e.id = o.employee_id
            {where}
            ORDER BY o.work_date DESC, o.id DESC
            """,
            tuple(parameters),
        )

    def save(
        self,
        employee_id: int,
        work_date: str,
        start_time: str,
        end_time: str,
        hours: str | float,
        shift_type: str,
        activity: str = "",
        authorized: bool = False,
        notes: str = "",
        overtime_id: int | None = None,
        period: str = "",
        authorized_by: str = "",
        approved_by: str = "",
        total_hours: str | float | None = None,
        lunch_hour_worked: bool | None = None,
        sunday_holiday: str = "",
        reported_surcharge: str = "",
    ) -> int:
        if not valid_date(work_date.strip()):
            raise ValueError("La fecha debe tener formato AAAA-MM-DD.")
        for label, value in (("inicio", start_time), ("fin", end_time)):
            if not valid_time(value.strip()):
                raise ValueError(f"La hora de {label} debe tener formato HH:MM.")
        try:
            hours_value = float(hours)
        except (ValueError, TypeError) as error:
            raise ValueError("Ingrese la cantidad de horas como número.") from error
        if not 0 < hours_value <= 24:
            raise ValueError("La cantidad de horas debe ser mayor que 0 y hasta 24.")
        total_hours_value: float | None = None
        if total_hours not in (None, ""):
            try:
                total_hours_value = float(total_hours)
            except (ValueError, TypeError) as error:
                raise ValueError("El total de horas reportado debe ser numérico.") from error
            if not 0 < total_hours_value <= 24:
                raise ValueError(
                    "El total de horas reportado debe ser mayor que 0 y hasta 24."
                )
        if shift_type not in SHIFT_TYPES:
            raise ValueError("Seleccione un tipo de jornada válido.")
        start = datetime.strptime(start_time.strip(), "%H:%M")
        end = datetime.strptime(end_time.strip(), "%H:%M")
        if end == start:
            raise ValueError("La hora de inicio y fin no pueden ser iguales.")

        values = (
            employee_id,
            work_date.strip(),
            start_time.strip(),
            end_time.strip(),
            hours_value,
            shift_type,
            activity.strip(),
            int(authorized),
            period.strip(),
            authorized_by.strip(),
            approved_by.strip(),
            total_hours_value,
            reported_surcharge.strip(),
            sunday_holiday.strip(),
            None if lunch_hour_worked is None else int(lunch_hour_worked),
            notes.strip(),
        )
        if overtime_id is None:
            cursor = self.database.execute(
                """
                INSERT INTO overtime (
                    employee_id, work_date, start_time, end_time, hours,
                    shift_type, activity, authorized, period, authorized_by,
                    approved_by, total_hours, reported_surcharge, sunday_holiday,
                    lunch_hour_worked, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            return int(cursor.lastrowid)
        self.database.execute(
            """
            UPDATE overtime SET employee_id = ?, work_date = ?,
                start_time = ?, end_time = ?, hours = ?, shift_type = ?,
                activity = ?, authorized = ?, period = ?, authorized_by = ?,
                approved_by = ?, total_hours = ?, reported_surcharge = ?,
                sunday_holiday = ?, lunch_hour_worked = ?, notes = ?
            WHERE id = ?
            """,
            (*values, overtime_id),
        )
        return overtime_id

    def delete(self, overtime_id: int) -> None:
        cursor = self.database.execute(
            "DELETE FROM overtime WHERE id = ?",
            (overtime_id,),
        )
        if cursor.rowcount == 0:
            raise ValueError("El registro de horas extra seleccionado ya no existe.")
