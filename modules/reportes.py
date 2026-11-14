from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from database import Database


class ReportService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def summary(self) -> dict[str, int]:
        return {
            "employees": self._count("employees", "active = 1"),
            "attendance": self._count("attendance"),
            "permissions_pending": self._count(
                "permissions", "status = 'Pendiente'"
            ),
            "overtime": self._count("overtime"),
        }

    def _count(self, table: str, condition: str = "") -> int:
        allowed = {"employees", "attendance", "permissions", "overtime"}
        if table not in allowed:
            raise ValueError("Tabla de informe no permitida.")
        where = f" WHERE {condition}" if condition else ""
        row = self.database.fetch_one(f"SELECT COUNT(*) AS total FROM {table}{where}")
        return int(row["total"]) if row else 0

    def export_csv(
        self, path: Path, records: list[dict[str, Any]], columns: list[str]
    ) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)

    def export_excel(
        self, path: Path, records: list[dict[str, Any]], columns: list[str]
    ) -> None:
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill
            from openpyxl.utils import get_column_letter
        except ImportError as error:
            raise RuntimeError(
                "La exportación Excel requiere openpyxl. Instale requirements.txt."
            ) from error

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Informe"
        sheet.append(columns)
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="24445C")
        for record in records:
            sheet.append([record.get(column, "") for column in columns])
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for column_index, column in enumerate(columns, start=1):
            longest = max(
                [len(str(column))]
                + [
                    len(str(record.get(column, "") or ""))
                    for record in records
                ]
            )
            sheet.column_dimensions[get_column_letter(column_index)].width = min(
                max(longest + 2, 12), 42
            )
        workbook.save(path)
