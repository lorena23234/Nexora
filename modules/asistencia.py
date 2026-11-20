from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from zipfile import BadZipFile

from database import Database
from modules.validaciones import (
    attendance_alerts,
    attendance_day_night_minutes,
    duplicate_key,
    valid_date,
)


SOURCE_TYPES = {
    "original_verificado",
    "transcripcion_documental",
    "datos_sinteticos",
    "no_verificada",
}

_COLUMN_ALIASES = {
    "employee_code": {
        "codigotrabajador",
        "codigoempleado",
        "codigointerno",
        "codigo",
        "employeecode",
    },
    "work_date": {"fecha", "fechatrabajo", "date", "workdate"},
    "entry_time": {"entrada", "entrada1", "horaentrada", "entrytime"},
    "exit_time": {"salida", "salida1", "horasalida", "exittime"},
    "source": {"fuente", "source", "origen"},
}


@dataclass(frozen=True)
class ImportRow:
    row_number: int
    values: dict[str, Any]
    raw: dict[str, Any]
    group_key: str = ""


@dataclass(frozen=True)
class ImportDataset:
    path: Path
    headers: tuple[str, ...]
    rows: tuple[ImportRow, ...]
    groups: dict[str, str]
    sheet_name: str
    grouped_report: bool = False


class AttendanceService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def add(
        self,
        employee_code: str,
        work_date: str,
        entry_time: str = "",
        exit_time: str = "",
        source: str = "Registro manual",
    ) -> int:
        code = employee_code.strip()
        employee = (
            self.database.fetch_one(
                "SELECT id, code FROM employees WHERE code = ? COLLATE NOCASE",
                (code,),
            )
            if code
            else None
        )
        cursor = self.database.execute(
            """
            INSERT INTO attendance (
                employee_id, employee_code, work_date, entry_time, exit_time, source
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                employee["id"] if employee else None,
                employee["code"] if employee else code,
                work_date.strip(),
                entry_time.strip(),
                exit_time.strip(),
                source.strip(),
            ),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def _normalize_header(value: Any) -> str:
        text = unicodedata.normalize("NFKD", str(value or ""))
        text = "".join(char for char in text if not unicodedata.combining(char))
        return re.sub(r"[^a-z0-9]", "", text.lower())

    @classmethod
    def _is_sensitive_header(cls, value: Any) -> bool:
        header = cls._normalize_header(value)
        return (
            any(
                token in header
                for token in (
                    "nombre",
                    "name",
                    "surname",
                    "email",
                    "correo",
                    "mail",
                    "telefono",
                    "celular",
                    "phone",
                    "mobile",
                    "direccion",
                    "address",
                    "domicilio",
                    "nacimiento",
                    "birth",
                    "edad",
                    "salary",
                    "salario",
                    "cedula",
                    "ident",
                    "documento",
                    "document",
                    "pasaporte",
                    "passport",
                    "nationalid",
                    "personalid",
                    "personalnumber",
                    "autorizadopor",
                    "aprobadopor",
                    "solicitante",
                    "firmante",
                    "responsable",
                    "supervisor",
                    "jefeinmediato",
                    "firma",
                )
            )
            or (
                "codigo" not in header
                and header in {"empleado", "trabajador", "employee", "worker"}
            )
            or header in {"id", "cc", "dni", "nit"}
            or header.startswith(
                (
                    "idpersonal",
                    "idempleado",
                    "idtrabajador",
                    "idpersona",
                    "idnumber",
                    "employeeid",
                    "personid",
                    "workerid",
                )
            )
        )

    @classmethod
    def _unique_headers(cls, values: tuple[Any, ...] | list[Any]) -> list[str]:
        headers: list[str] = []
        seen: dict[str, int] = {}
        for index, value in enumerate(values, start=1):
            name = str(value).strip() if value is not None else ""
            name = name or f"Columna {index}"
            count = seen.get(name, 0) + 1
            seen[name] = count
            headers.append(name if count == 1 else f"{name} ({count})")
        return headers

    @classmethod
    def _header_mapping(cls, headers: list[str]) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for field, aliases in _COLUMN_ALIASES.items():
            match = next(
                (
                    header
                    for header in headers
                    if cls._normalize_header(header) in aliases
                ),
                "",
            )
            mapping[field] = match
        return mapping

    @classmethod
    def _header_row_indexes(cls, rows: list[tuple[Any, ...]]) -> list[int]:
        indexes: list[int] = []
        for index, row in enumerate(rows):
            headers = cls._unique_headers(list(row))
            mapping = cls._header_mapping(headers)
            if mapping["work_date"] and mapping["entry_time"] and mapping["exit_time"]:
                indexes.append(index)
        return indexes

    @staticmethod
    def _plain_cell(value: Any) -> Any:
        if isinstance(value, (datetime, date, time)):
            return value.isoformat()
        return value

    @staticmethod
    def _cell_text(value: Any, field: str) -> str:
        if value is None:
            return ""
        if field == "work_date" and isinstance(value, (datetime, date)):
            return value.strftime("%Y-%m-%d")
        if field in {"entry_time", "exit_time"} and isinstance(value, (datetime, time)):
            return value.strftime("%H:%M")
        text = str(value).strip()
        if field == "work_date":
            for pattern in (
                "%Y-%m-%d",
                "%Y/%m/%d",
                "%d/%m/%Y",
                "%d/%m/%y",
                "%d-%m-%Y",
            ):
                try:
                    return datetime.strptime(text, pattern).strftime("%Y-%m-%d")
                except ValueError:
                    continue
        if field in {"entry_time", "exit_time"}:
            for pattern in (
                "%H:%M",
                "%H:%M:%S",
                "%I:%M %p",
                "%I:%M:%S %p",
                "%Y/%m/%d %H:%M",
                "%Y/%m/%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d %H:%M:%S",
                "%d/%m/%Y %H:%M",
                "%d/%m/%Y %H:%M:%S",
            ):
                try:
                    return datetime.strptime(
                        text.upper(), pattern
                    ).strftime("%H:%M")
                except ValueError:
                    continue
        return text

    @staticmethod
    def _raw_row(
        headers: list[str], values: tuple[Any, ...]
    ) -> dict[str, Any]:
        raw: dict[str, Any] = {
            header: AttendanceService._plain_cell(values[index])
            for index, header in enumerate(headers)
            if index < len(values)
        }
        raw["_original_row"] = [
            AttendanceService._plain_cell(value) for value in values
        ]
        return raw

    @classmethod
    def _read_xlsx(
        cls, path: Path, sheet_name: str | None = None
    ) -> ImportDataset:
        try:
            from openpyxl import load_workbook
            from openpyxl.utils.exceptions import InvalidFileException
        except ImportError as error:
            raise RuntimeError(
                "La importación Excel requiere openpyxl. Instale requirements.txt."
            ) from error
        try:
            workbook = load_workbook(path, read_only=True, data_only=True)
        except (BadZipFile, InvalidFileException) as error:
            raise ValueError("El archivo seleccionado no es un Excel .xlsx válido.") from error

        try:
            if sheet_name and sheet_name not in workbook.sheetnames:
                raise ValueError("La hoja seleccionada no existe en el archivo.")
            sheet = workbook[sheet_name] if sheet_name else workbook.active
            values = [tuple(row) for row in sheet.iter_rows(values_only=True)]
            nonempty = [
                index
                for index, row in enumerate(values)
                if any(value not in (None, "") for value in row)
            ]
            if not nonempty:
                raise ValueError("La hoja seleccionada no contiene datos.")

            headers_found = cls._header_row_indexes(values)
            header_row_index = headers_found[0] if headers_found else nonempty[0]
            all_headers = cls._unique_headers(list(values[header_row_index]))
            safe_positions = [
                index
                for index, header in enumerate(all_headers)
                if not cls._is_sensitive_header(header)
            ]
            headers = [all_headers[index] for index in safe_positions]
            if not headers:
                raise ValueError(
                    "La hoja no contiene columnas permitidas para importar."
                )
            safe_values = [
                tuple(row[index] if index < len(row) else None for index in safe_positions)
                for row in values
            ]
            if len(headers_found) > 1:
                first_signature = tuple(cls._normalize_header(value) for value in all_headers)
                repeated = [
                    index
                    for index in headers_found
                    if tuple(
                        cls._normalize_header(value)
                        for value in cls._unique_headers(list(values[index]))
                    )
                    == first_signature
                ]
                if len(repeated) > 1:
                    return cls._read_grouped_report(
                        path, sheet.title, safe_values, headers, repeated
                    )

            header_index = header_row_index
            rows: list[ImportRow] = []
            for index in range(header_index + 1, len(values)):
                source_values = safe_values[index]
                if not any(value not in (None, "") for value in source_values):
                    continue
                row_values = {
                    header: source_values[column] if column < len(source_values) else None
                    for column, header in enumerate(headers)
                }
                if cls._normalize_header(" ".join(str(value or "") for value in source_values)) == "":
                    continue
                rows.append(
                    ImportRow(
                        row_number=index + 1,
                        values=row_values,
                        raw=cls._raw_row(headers, source_values),
                    )
                )
            return ImportDataset(
                path=path,
                headers=tuple(headers),
                rows=tuple(rows),
                groups={},
                sheet_name=sheet.title,
            )
        finally:
            workbook.close()

    @classmethod
    def _read_grouped_report(
        cls,
        path: Path,
        sheet_name: str,
        rows: list[tuple[Any, ...]],
        headers: list[str],
        header_indexes: list[int],
    ) -> ImportDataset:
        groups: dict[str, str] = {}
        records: list[ImportRow] = []
        mapping = cls._header_mapping(headers)
        date_index = headers.index(mapping["work_date"])
        entry_index = headers.index(mapping["entry_time"])
        exit_index = headers.index(mapping["exit_time"])

        for group_number, header_index in enumerate(header_indexes):
            group_key = str(header_index + 1)
            group_label = f"Grupo de empleado {group_number + 1}"
            groups[group_key] = group_label
            next_header = (
                header_indexes[group_number + 1]
                if group_number + 1 < len(header_indexes)
                else len(rows)
            )
            for index in range(header_index + 1, next_header):
                values = rows[index]
                if any(
                    isinstance(value, str) and value.strip().upper() == "TOTAL"
                    for value in values
                ):
                    break
                if not any(value not in (None, "") for value in values):
                    continue
                date_value = values[date_index] if date_index < len(values) else None
                entry_value = values[entry_index] if entry_index < len(values) else None
                exit_value = values[exit_index] if exit_index < len(values) else None
                if all(value in (None, "") for value in (date_value, entry_value, exit_value)):
                    continue
                row_values = {
                    header: values[column] if column < len(values) else None
                    for column, header in enumerate(headers)
                }
                records.append(
                    ImportRow(
                        row_number=index + 1,
                        values=row_values,
                        raw=cls._raw_row(headers, values),
                        group_key=group_key,
                    )
                )
        if not records:
            raise ValueError("No se encontraron marcaciones en los bloques del reporte.")
        return ImportDataset(
            path=path,
            headers=tuple(headers),
            rows=tuple(records),
            groups=groups,
            sheet_name=sheet_name,
            grouped_report=True,
        )

    @classmethod
    def read_import_source(
        cls, path: Path, sheet_name: str | None = None
    ) -> ImportDataset:
        path = Path(path)
        if not path.is_file():
            raise OSError("No se encuentra el archivo seleccionado.")
        if path.suffix.lower() == ".xlsx":
            return cls._read_xlsx(path, sheet_name)
        if path.suffix.lower() != ".csv":
            raise ValueError("Seleccione un archivo CSV o Excel .xlsx.")
        if sheet_name:
            raise ValueError("Los archivos CSV no contienen hojas.")
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as file:
                source_rows = list(csv.reader(file))
        except csv.Error as error:
            raise ValueError("El archivo CSV no tiene un formato válido.") from error
        header_index = next(
            (
                index
                for index, row in enumerate(source_rows)
                if any(value.strip() for value in row)
            ),
            None,
        )
        if header_index is None:
            raise ValueError("El CSV no contiene encabezados.")
        all_headers = cls._unique_headers(source_rows[header_index])
        safe_positions = [
            index
            for index, header in enumerate(all_headers)
            if not cls._is_sensitive_header(header)
        ]
        headers = [all_headers[index] for index in safe_positions]
        if not headers:
            raise ValueError("El CSV no contiene columnas permitidas para importar.")
        records: list[ImportRow] = []
        for index, source_values in enumerate(source_rows[header_index + 1 :], start=header_index + 2):
            if not any(value.strip() for value in source_values):
                continue
            if len(source_values) > len(all_headers):
                raise ValueError(
                    f"La fila {index} tiene más columnas que el encabezado."
                )
            safe_values = tuple(
                source_values[column] if column < len(source_values) else ""
                for column in safe_positions
            )
            row_values = {
                header: safe_values[column]
                for column, header in enumerate(headers)
            }
            records.append(
                ImportRow(
                    row_number=index,
                    values=row_values,
                    raw=cls._raw_row(headers, safe_values),
                )
            )
        return ImportDataset(
            path=path,
            headers=tuple(headers),
            rows=tuple(records),
            groups={},
            sheet_name="CSV",
        )

    @staticmethod
    def available_sheets(path: Path) -> tuple[str, ...]:
        if path.suffix.lower() != ".xlsx":
            return ("CSV",)
        try:
            from openpyxl import load_workbook
            from openpyxl.utils.exceptions import InvalidFileException
        except ImportError as error:
            raise RuntimeError(
                "La importación Excel requiere openpyxl. Instale requirements.txt."
            ) from error
        try:
            workbook = load_workbook(path, read_only=True, data_only=True)
        except (BadZipFile, InvalidFileException) as error:
            raise ValueError("El archivo seleccionado no es un Excel .xlsx válido.") from error
        try:
            return tuple(workbook.sheetnames)
        finally:
            workbook.close()

    @staticmethod
    def guess_mapping(headers: tuple[str, ...] | list[str]) -> dict[str, str]:
        return AttendanceService._header_mapping(list(headers))

    def preview_import(
        self,
        dataset: ImportDataset,
        mapping: dict[str, str],
        group_assignments: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        group_assignments = group_assignments or {}
        valid_headers = set(dataset.headers)
        for field in ("work_date", "entry_time", "exit_time", "employee_code", "source"):
            header = mapping.get(field, "")
            if header and header not in valid_headers:
                raise ValueError(f"La columna seleccionada para {field} no existe.")
            if header and self._is_sensitive_header(header):
                raise ValueError(
                    "No se permite mapear columnas que puedan contener datos personales."
                )

        existing_rows = self.database.fetch_all(
            """
            SELECT employee_code, work_date, entry_time, exit_time
            FROM attendance
            """
        )
        existing_keys: set[tuple[str, str, str, str]] = set()
        for item in existing_rows:
            key = duplicate_key(item)
            if key[0]:
                existing_keys.add(key)

        preview: list[dict[str, Any]] = []
        imported_keys: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
        for row in dataset.rows:
            values = row.values
            code_header = mapping.get("employee_code", "")
            code_value = (
                self._cell_text(values.get(code_header), "employee_code")
                if code_header
                else group_assignments.get(row.group_key, "")
            )
            date_header = mapping.get("work_date", "")
            entry_header = mapping.get("entry_time", "")
            exit_header = mapping.get("exit_time", "")
            work_date = self._cell_text(values.get(date_header), "work_date") if date_header else ""
            entry_time = self._cell_text(values.get(entry_header), "entry_time") if entry_header else ""
            exit_time = self._cell_text(values.get(exit_header), "exit_time") if exit_header else ""
            employee = (
                self.database.fetch_one(
                    "SELECT id, code FROM employees WHERE code = ? COLLATE NOCASE",
                    (code_value.strip(),),
                )
                if code_value.strip()
                else None
            )
            record = {
                "employee_id": employee["id"] if employee else None,
                "employee_code": employee["code"] if employee else code_value.strip(),
                "work_date": work_date,
                "original_work_date": self._plain_cell(
                    values.get(date_header) if date_header else None
                ),
                "entry_time": entry_time,
                "original_entry_time": self._plain_cell(
                    values.get(entry_header) if entry_header else None
                ),
                "exit_time": exit_time,
                "original_exit_time": self._plain_cell(
                    values.get(exit_header) if exit_header else None
                ),
                "source": "Importación",
                "source_row": row.row_number,
                "group_key": row.group_key,
                "group_label": dataset.groups.get(row.group_key, ""),
                "raw_data": {
                    header: self._plain_cell(values.get(header))
                    for header in dict.fromkeys(
                        mapping[field]
                        for field in (
                            "employee_code",
                            "work_date",
                            "entry_time",
                            "exit_time",
                        )
                        if mapping.get(field)
                    )
                },
            }
            self._add_day_night_durations(record)
            record["raw_data"]["_original_row"] = list(
                record["raw_data"].values()
            )
            alerts = attendance_alerts(record)
            key = duplicate_key(record)
            if key[0] and key[1] and (key[2] or key[3]):
                previous = imported_keys.get(key, [])
                if key in existing_keys or previous:
                    alerts.append("Posible duplicidad: registro coincidente")
                    for prior in previous:
                        if "Posible duplicidad: registro coincidente" not in prior["alerts"]:
                            prior["alerts"].append(
                                "Posible duplicidad: registro coincidente"
                            )
            record["alerts"] = alerts
            if key[0] and key[1] and (key[2] or key[3]):
                imported_keys.setdefault(key, []).append(record)
            preview.append(record)
        return preview

    def import_reviewed(
        self,
        dataset: ImportDataset,
        mapping: dict[str, str],
        source_type: str,
        group_assignments: dict[str, str] | None = None,
    ) -> dict[str, int]:
        if source_type not in SOURCE_TYPES:
            raise ValueError("Seleccione una clasificación de fuente válida.")
        preview = self.preview_import(dataset, mapping, group_assignments)
        if not preview:
            raise ValueError("No hay filas para importar.")
        digest = hashlib.sha256()
        with dataset.path.open("rb") as source_file:
            for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
                digest.update(chunk)
        batch_mapping = {
            "columns": {
                field: mapping.get(field, "")
                for field in (
                    "employee_code",
                    "work_date",
                    "entry_time",
                    "exit_time",
                )
            },
            "employee_groups": group_assignments or {},
            "sheet": dataset.sheet_name,
        }
        source_labels = {
            "original_verificado": "Original verificado",
            "transcripcion_documental": "Transcripción documental",
            "datos_sinteticos": "Datos sintéticos",
            "no_verificada": "Sin verificar",
        }

        with self.database.connection:
            cursor = self.database.connection.execute(
                """
                INSERT INTO attendance_imports (
                    source_name, source_sha256, source_type, mapping_json
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    "archivo.xlsx" if dataset.path.suffix.lower() == ".xlsx" else "archivo.csv",
                    digest.hexdigest(),
                    source_type,
                    json.dumps(batch_mapping, ensure_ascii=False, sort_keys=True),
                ),
            )
            batch_id = int(cursor.lastrowid)
            insert_rows: list[tuple[Any, ...]] = []
            for record in preview:
                raw_data = json.dumps(
                    {
                        "row": record["raw_data"],
                        "employee_group": record["group_label"],
                    },
                    ensure_ascii=False,
                    default=self._plain_cell,
                )
                insert_rows.append(
                    (
                        record["employee_id"],
                        record["employee_code"],
                        record["work_date"],
                        record["entry_time"],
                        record["exit_time"],
                        source_labels[source_type],
                        batch_id,
                        record["source_row"],
                        raw_data,
                    )
                )
            self.database.connection.executemany(
                """
                INSERT INTO attendance (
                    employee_id, employee_code, work_date, entry_time, exit_time,
                    source, import_batch_id, source_row, raw_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                insert_rows,
            )

        return {
            "batch_id": batch_id,
            "imported": len(preview),
            "invalid": sum(
                any(not alert.startswith("Posible duplicidad:") for alert in item["alerts"])
                for item in preview
            ),
            "duplicates": sum(
                any(alert.startswith("Posible duplicidad:") for alert in item["alerts"])
                for item in preview
            ),
            "unmatched": sum(
                any("sin empleado asociado" in alert.lower() for alert in item["alerts"])
                for item in preview
            ),
        }

    def _legacy_import(self, path: Path) -> int:
        dataset = self.read_import_source(path)
        mapping = self.guess_mapping(dataset.headers)
        required = ("employee_code", "work_date", "entry_time", "exit_time")
        missing = [field for field in required if not mapping.get(field)]
        if missing:
            labels = {
                "employee_code": "codigo_trabajador",
                "work_date": "fecha",
                "entry_time": "entrada",
                "exit_time": "salida",
            }
            raise ValueError(
                "Faltan columnas requeridas: "
                + ", ".join(sorted(labels[field] for field in missing))
            )
        return self.import_reviewed(dataset, mapping, "no_verificada")["imported"]

    def import_csv(self, path: Path) -> int:
        if path.suffix.lower() != ".csv":
            raise ValueError("Seleccione un archivo CSV.")
        return self._legacy_import(path)

    def import_excel(self, path: Path) -> int:
        if path.suffix.lower() != ".xlsx":
            raise ValueError("Seleccione un archivo Excel .xlsx.")
        return self._legacy_import(path)

    def list(
        self,
        employee_id: int | None = None,
        start_date: str = "",
        end_date: str = "",
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        parameters: list[Any] = []
        if employee_id is not None:
            conditions.append("a.employee_id = ?")
            parameters.append(employee_id)
        if start_date:
            conditions.append("a.work_date >= ?")
            parameters.append(start_date)
        if end_date:
            conditions.append("a.work_date <= ?")
            parameters.append(end_date)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        records = self.database.fetch_all(
            f"""
            SELECT a.id, a.employee_id, a.employee_code, a.work_date,
                   a.entry_time, a.exit_time, a.source, a.import_batch_id,
                   a.source_row, a.created_at,
                   COALESCE(e.name, 'Sin asociación') AS employee_name
            FROM attendance a
            LEFT JOIN employees e ON e.id = a.employee_id
            {where}
            ORDER BY a.work_date DESC, a.entry_time, a.id
            """,
            tuple(parameters),
        )

        seen: dict[tuple[str, str, str, str], list[int]] = {}
        for index, record in enumerate(records):
            self._add_day_night_durations(record)
            alerts = attendance_alerts(record)
            key = duplicate_key(record)
            if key[0] and key[1] and (key[2] or key[3]):
                seen.setdefault(key, []).append(index)
            record["alerts"] = alerts
        for indexes in seen.values():
            if len(indexes) > 1:
                for index in indexes:
                    records[index]["alerts"].append(
                        "Posible duplicidad: registro coincidente"
                    )
        return records

    def delete(self, attendance_id: int) -> None:
        cursor = self.database.execute(
            "DELETE FROM attendance WHERE id = ?",
            (attendance_id,),
        )
        if cursor.rowcount == 0:
            raise ValueError("La marcación seleccionada ya no existe.")

    def export_csv(self, path: Path, records: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(
                (
                    "codigo_trabajador",
                    "fecha",
                    "entrada",
                    "salida",
                    "horas_diurnas",
                    "horas_nocturnas",
                    "observaciones",
                )
            )
            for record in records:
                writer.writerow(
                    (
                        record["employee_code"],
                        record["work_date"],
                        record["entry_time"],
                        record["exit_time"],
                        record.get("daytime_duration", ""),
                        record.get("nighttime_duration", ""),
                        "; ".join(record["alerts"]),
                    )
                )

    @staticmethod
    def _add_day_night_durations(record: dict[str, Any]) -> None:
        durations = attendance_day_night_minutes(
            str(record.get("entry_time", "")),
            str(record.get("exit_time", "")),
        )
        if durations is None:
            record["daytime_duration"] = ""
            record["nighttime_duration"] = ""
            return
        record["daytime_duration"] = f"{durations[0] // 60:02}:{durations[0] % 60:02}"
        record["nighttime_duration"] = f"{durations[1] // 60:02}:{durations[1] % 60:02}"

    @staticmethod
    def validate_period(start_date: str, end_date: str) -> None:
        for value in (start_date, end_date):
            if value and not valid_date(value):
                raise ValueError("Use fechas válidas con formato AAAA-MM-DD.")
        if start_date and end_date and date.fromisoformat(start_date) > date.fromisoformat(end_date):
            raise ValueError("La fecha inicial no puede ser posterior a la fecha final.")
