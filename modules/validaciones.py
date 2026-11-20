from __future__ import annotations

import re
from datetime import datetime
from typing import Any


def valid_date(value: str) -> bool:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def valid_time(value: str) -> bool:
    if not re.fullmatch(r"\d{2}:\d{2}", value):
        return False
    try:
        datetime.strptime(value, "%H:%M")
    except ValueError:
        return False
    return True


def attendance_alerts(record: dict[str, Any]) -> list[str]:
    alerts: list[str] = []
    if not record.get("employee_id"):
        alerts.append("Código sin empleado asociado")
    if not str(record.get("work_date", "")).strip():
        alerts.append("Falta la fecha")
    elif not valid_date(str(record["work_date"]).strip()):
        alerts.append("Fecha no reconocida (use AAAA-MM-DD)")

    entry = str(record.get("entry_time", "")).strip()
    exit_time = str(record.get("exit_time", "")).strip()
    if not entry:
        alerts.append("Falta la hora de entrada")
    elif not valid_time(entry):
        alerts.append("Hora de entrada no reconocida (use HH:MM)")

    if not exit_time:
        alerts.append("Falta la hora de salida")
    elif not valid_time(exit_time):
        alerts.append("Hora de salida no reconocida (use HH:MM)")

    if entry and exit_time and valid_time(entry) and valid_time(exit_time):
        if entry == exit_time:
            alerts.append("Entrada y salida tienen la misma hora")
        elif exit_time < entry and record.get("work_date"):
            alerts.append(
                "La salida es anterior a la entrada; posible cruce de medianoche "
                "o inconsistencia, verificar jornada"
            )
    return alerts


def duplicate_key(record: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(record.get("employee_code", "")).strip().casefold(),
        str(record.get("work_date", "")).strip(),
        str(record.get("entry_time", "")).strip(),
        str(record.get("exit_time", "")).strip(),
    )
