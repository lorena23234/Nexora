from __future__ import annotations

import csv
import json
import sqlite3
import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from tkinter import ttk

import pytest

from database import Database
from modules.asistencia import AttendanceService, ImportDataset, ImportRow
from modules.empleados import EmployeeService
from modules.horas_extras import OvertimeService
from modules.permisos import PermissionService
from modules.reportes import ReportService
from modules.validaciones import attendance_alerts, valid_date, valid_time
from views.estilos import IconActionButton, draw_brand_mark, draw_icon
from views.ventana_principal import MainWindow


@pytest.fixture
def database(tmp_path):
    database = Database(tmp_path / "test.db")
    yield database
    database.close()


@pytest.fixture
def employee(database):
    return EmployeeService(database).save(
        "TEST-001", "Persona Ficticia", "Auxiliar", "Obra de prueba"
    )


def test_database_creates_normalized_tables_and_enables_foreign_keys(database):
    tables = {
        row["name"]
        for row in database.fetch_all(
            "SELECT name FROM sqlite_master WHERE type = ?", ("table",)
        )
    }

    assert {"employees", "attendance", "permissions", "overtime"} <= tables
    assert database.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_employee_create_search_edit_and_deactivate(database):
    service = EmployeeService(database)
    employee_id = service.save("TEST-001", "Persona Ficticia", "Auxiliar", "Obra A")

    found = service.list("test-001")
    assert len(found) == 1
    assert found[0]["id"] == employee_id

    service.save("TEST-001", "Nombre Actualizado", "Técnico", "Obra B", employee_id)
    assert service.get(employee_id)["name"] == "Nombre Actualizado"
    assert service.get(employee_id)["department"] == "Obra B"

    service.set_active(employee_id, False)
    assert service.list(include_inactive=False) == []
    assert service.list()[0]["active"] == 0


def test_employee_rejects_duplicate_code_and_sql_like_search(database):
    service = EmployeeService(database)
    service.save("TEST-001", "Persona Ficticia")
    with pytest.raises(ValueError, match="Ya existe"):
        service.save("test-001", "Otra Persona Ficticia")

    assert service.list("' OR 1=1 --") == []


def test_employee_delete_requires_no_attendance_or_novelty_history(
    database, employee
):
    service = EmployeeService(database)
    service.delete(employee)
    assert service.get(employee) is None

    employee = service.save("TEST-002", "Persona Ficticia")
    AttendanceService(database).add(
        "TEST-002", "2026-10-25", "08:00", "17:00"
    )
    with pytest.raises(ValueError, match="historial asociado"):
        service.delete(employee)
    assert service.get(employee) is not None

    attendance = database.fetch_one("SELECT id FROM attendance")
    AttendanceService(database).delete(attendance["id"])
    service.delete(employee)
    assert service.get(employee) is None


def test_employee_create_get_and_list_with_trimmed_values(database):
    service = EmployeeService(database)

    employee_id = service.save(
        "  DEMO-EMP-001  ",
        "  Persona Sintética Uno  ",
        "  Auxiliar  ",
        "  Área de prueba  ",
    )

    assert service.get(employee_id) == {
        "id": employee_id,
        "code": "DEMO-EMP-001",
        "name": "Persona Sintética Uno",
        "position": "Auxiliar",
        "department": "Área de prueba",
        "active": 1,
    }
    assert [row["id"] for row in service.list()] == [employee_id]


def test_employee_search_matches_code_or_name_and_respects_active_filter(database):
    service = EmployeeService(database)
    active_id = service.save(
        "DEMO-EMP-002", "Persona Sintética Dos", "Operaria", "Área A"
    )
    inactive_id = service.save(
        "DEMO-EMP-003", "Persona Sintética Tres", "Técnica", "Área B"
    )
    service.set_active(inactive_id, False)

    assert [row["id"] for row in service.list("demo-emp-002")] == [active_id]
    assert [row["id"] for row in service.list("sintética tres")] == [inactive_id]
    assert [row["id"] for row in service.list(include_inactive=False)] == [active_id]
    service.set_active(inactive_id, True)
    assert [row["id"] for row in service.list(include_inactive=False)] == [
        active_id,
        inactive_id,
    ]


def test_employee_edit_updates_fields_without_changing_identity(database):
    service = EmployeeService(database)
    employee_id = service.save(
        "DEMO-EMP-004", "Persona Sintética Cuatro", "Auxiliar", "Área A"
    )

    returned_id = service.save(
        "DEMO-EMP-004",
        "  Persona Actualizada  ",
        "  Técnica  ",
        "  Área B  ",
        employee_id,
    )

    assert returned_id == employee_id
    updated = service.get(employee_id)
    assert updated is not None
    assert updated["name"] == "Persona Actualizada"
    assert updated["position"] == "Técnica"
    assert updated["department"] == "Área B"
    assert len(service.list()) == 1


def test_employee_save_rejects_missing_required_values_and_duplicate_code(database):
    service = EmployeeService(database)
    with pytest.raises(ValueError, match="obligatorios"):
        service.save(" ", "Persona Sintética")
    with pytest.raises(ValueError, match="obligatorios"):
        service.save("DEMO-EMP-005", " ")

    employee_id = service.save("DEMO-EMP-005", "Persona Sintética Cinco")
    with pytest.raises(ValueError, match="Ya existe"):
        service.save("demo-emp-005", "Otra Persona Sintética")
    saved = service.get(employee_id)
    assert saved is not None
    assert saved["name"] == "Persona Sintética Cinco"
    assert len(service.list()) == 1


def test_employee_delete_blocks_any_history_and_allows_unreferenced_employee(database):
    service = EmployeeService(database)
    employee_id = service.save(
        "DEMO-EMP-006", "Persona Sintética Seis", "Operaria", "Área C"
    )
    database.execute(
        "INSERT INTO attendance (employee_id, employee_code, work_date) "
        "VALUES (?, ?, ?)",
        (employee_id, "DEMO-EMP-006", "2026-11-13"),
    )
    database.execute(
        """
        INSERT INTO permissions (
            employee_id, requested_on, start_date, start_time,
            end_date, end_time, permission_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            employee_id,
            "2026-11-13",
            "2026-11-14",
            "09:00",
            "2026-11-14",
            "10:00",
            "Cita sintética",
        ),
    )
    database.execute(
        """
        INSERT INTO overtime (
            employee_id, work_date, start_time, end_time, hours, shift_type
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (employee_id, "2026-11-13", "17:00", "18:00", 1, "Diurna"),
    )

    with pytest.raises(ValueError, match="historial asociado"):
        service.delete(employee_id)
    assert service.get(employee_id) is not None

    for table in ("attendance", "permissions", "overtime"):
        database.execute(f"DELETE FROM {table} WHERE employee_id = ?", (employee_id,))
    service.delete(employee_id)
    assert service.get(employee_id) is None


def test_attendance_save_filter_and_missing_field_alerts(database, employee):
    service = AttendanceService(database)
    service.add("TEST-001", "2026-10-25", "08:00", "")
    service.add("TEST-001", "2026-10-26", "08:00", "17:00")

    results = service.list(employee_id=employee, start_date="2026-10-25", end_date="2026-10-25")
    assert len(results) == 1
    assert results[0]["employee_name"] == "Persona Ficticia"
    assert "Falta la hora de salida" in results[0]["alerts"]


def test_unmatched_imported_employee_is_kept_and_alerted(database):
    service = AttendanceService(database)
    service.add("NO-REGISTRADO", "2026-10-25", "08:00", "17:00")

    result = service.list()[0]
    assert result["employee_code"] == "NO-REGISTRADO"
    assert result["employee_id"] is None
    assert "Código sin empleado asociado" in result["alerts"]


def test_attendance_duplicates_flag_both_rows_without_deleting(database, employee):
    assert employee > 0
    service = AttendanceService(database)
    for _ in range(2):
        service.add("TEST-001", "2026-10-25", "08:00", "17:00")

    results = service.list()
    assert len(results) == 2
    assert all(
        "Posible duplicidad: registro coincidente" in item["alerts"]
        for item in results
    )


def test_overnight_attendance_is_flagged_without_changing_reported_values(
    database, employee
):
    service = AttendanceService(database)
    service.add("TEST-001", "2026-10-25", "22:00", "06:00")

    record = service.list()[0]

    assert record["employee_id"] == employee
    assert record["work_date"] == "2026-10-25"
    assert record["entry_time"] == "22:00"
    assert record["exit_time"] == "06:00"
    assert (
        "La salida es anterior a la entrada; posible cruce de medianoche "
        "o inconsistencia, verificar jornada"
    ) in record["alerts"]


def test_distinct_same_day_attendance_periods_are_not_flagged_as_duplicates(
    database, employee
):
    service = AttendanceService(database)
    service.add("TEST-001", "2026-10-25", "08:00", "12:00")
    service.add("TEST-001", "2026-10-25", "13:00", "17:00")

    records = service.list()

    assert len(records) == 2
    assert all(
        "Posible duplicidad: registro coincidente" not in record["alerts"]
        for record in records
    )
    assert {record["entry_time"] for record in records} == {"08:00", "13:00"}


def test_attendance_delete_removes_only_selected_row(database, employee):
    service = AttendanceService(database)
    first_id = service.add("TEST-001", "2026-10-25", "08:00", "17:00")
    service.add("TEST-001", "2026-10-26", "08:00", "17:00")

    service.delete(first_id)

    results = service.list()
    assert len(results) == 1
    assert results[0]["work_date"] == "2026-10-26"
    with pytest.raises(ValueError, match="ya no existe"):
        service.delete(first_id)


def test_attendance_flags_invalid_and_inconsistent_values(database):
    service = AttendanceService(database)
    service.add("", "31/10/2026", "18:00", "08:00")

    alerts = service.list()[0]["alerts"]
    assert "Código sin empleado asociado" in alerts
    assert "Fecha no reconocida (use AAAA-MM-DD)" in alerts
    assert (
        "La salida es anterior a la entrada; posible cruce de medianoche "
        "o inconsistencia, verificar jornada"
    ) in alerts


def test_csv_import_associates_known_code_and_preserves_unknown(tmp_path, database, employee):
    csv_path = tmp_path / "asistencia_sintetica.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(("codigo_trabajador", "fecha", "entrada", "salida"))
        writer.writerow(("TEST-001", "2026-10-25", "08:00", "17:00"))
        writer.writerow(("TEMP-999", "fecha inválida", "8am", ""))

    service = AttendanceService(database)
    assert service.import_csv(csv_path) == 2
    records = service.list()
    unknown = next(record for record in records if record["employee_code"] == "TEMP-999")
    known = next(record for record in records if record["employee_code"] == "TEST-001")
    assert unknown["employee_id"] is None
    assert unknown["source"] == "Sin verificar"
    assert any("Fecha no reconocida" in alert for alert in unknown["alerts"])
    assert known["employee_id"] == employee


def test_csv_invalid_header_does_not_import_partial_rows(tmp_path, database):
    csv_path = tmp_path / "malformado.csv"
    csv_path.write_text(
        "codigo_trabajador,fecha\nTEST-001,2026-10-25\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="Faltan columnas"):
        AttendanceService(database).import_csv(csv_path)
    assert database.fetch_one("SELECT COUNT(*) AS n FROM attendance")["n"] == 0


def test_csv_too_many_columns_is_atomic(tmp_path, database):
    csv_path = tmp_path / "malformado.csv"
    csv_path.write_text(
        "codigo_trabajador,fecha,entrada,salida\n"
        "TEST-001,2026-10-25,08:00,17:00\n"
        "TEST-002,2026-10-26,08:00,17:00,extra\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="más columnas"):
        AttendanceService(database).import_csv(csv_path)
    assert database.fetch_one("SELECT COUNT(*) AS n FROM attendance")["n"] == 0


def test_import_preview_mapping_duplicates_and_source_traceability(
    tmp_path, database, employee
):
    path = tmp_path / "transcripcion_sintetica.csv"
    path.write_text(
        "Código interno,Fecha,Entrada,Salida\n"
        "TEST-001,2026-10-25, 08:00 ,17:00\n"
        "TEST-001,fecha inválida,8am,\n",
        encoding="utf-8",
    )
    service = AttendanceService(database)
    service.add("TEST-001", "2026-10-25", "08:00", "17:00")
    dataset = service.read_import_source(path)
    mapping = service.guess_mapping(dataset.headers)

    assert mapping == {
        "employee_code": "Código interno",
        "work_date": "Fecha",
        "entry_time": "Entrada",
        "exit_time": "Salida",
        "source": "",
    }
    preview = service.preview_import(dataset, mapping)
    assert "Posible duplicidad: registro coincidente" in preview[0]["alerts"]
    assert any("Fecha no reconocida" in alert for alert in preview[1]["alerts"])
    assert preview[0]["entry_time"] == "08:00"

    result = service.import_reviewed(
        dataset, mapping, "transcripcion_documental"
    )
    assert result["imported"] == 2
    assert result["duplicates"] == 1
    assert result["invalid"] == 1
    assert result["unmatched"] == 0

    batch = database.fetch_one(
        "SELECT source_name, source_sha256, source_type FROM attendance_imports WHERE id = ?",
        (result["batch_id"],),
    )
    imported = database.fetch_one(
        """
        SELECT source_row, raw_data, import_batch_id, entry_time
        FROM attendance
        WHERE import_batch_id = ? AND source_row = ?
        """,
        (result["batch_id"], 2),
    )
    original = json.loads(imported["raw_data"])
    assert batch["source_name"] == "archivo.csv"
    assert len(batch["source_sha256"]) == 64
    assert batch["source_type"] == "transcripcion_documental"
    assert imported["import_batch_id"] == result["batch_id"]
    imported_record = database.fetch_one(
        "SELECT source FROM attendance WHERE import_batch_id = ? AND source_row = ?",
        (result["batch_id"], 2),
    )
    assert imported_record["source"] == "Transcripción documental"
    assert original["row"]["Entrada"] == " 08:00 "
    assert original["row"]["_original_row"][2] == " 08:00 "
    assert imported["entry_time"] == "08:00"
    assert employee > 0


def test_import_normalizes_known_formats_and_flags_both_intra_file_duplicates(
    tmp_path, database, employee
):
    path = tmp_path / "reloj_sintetico.csv"
    path.write_text(
        "codigo_trabajador,fecha,entrada,salida\n"
        "TEST-001,31/10/2026,8:00 AM,5:30 PM\n"
        "TEST-001,31/10/2026,8:00 AM,5:30 PM\n"
        "TEST-001,2026/10/31,2026/10/31 08:00:00,2026/10/31 17:30:00\n",
        encoding="utf-8",
    )
    service = AttendanceService(database)
    dataset = service.read_import_source(path)
    mapping = service.guess_mapping(dataset.headers)
    preview = service.preview_import(dataset, mapping)

    assert preview[0]["work_date"] == "2026-10-31"
    assert preview[0]["entry_time"] == "08:00"
    assert preview[0]["exit_time"] == "17:30"
    assert preview[0]["original_work_date"] == "31/10/2026"
    assert preview[0]["raw_data"]["fecha"] == "31/10/2026"
    assert preview[2]["work_date"] == "2026-10-31"
    assert preview[2]["entry_time"] == "08:00"
    assert preview[2]["raw_data"]["entrada"] == "2026/10/31 08:00:00"
    assert all(
        "Posible duplicidad: registro coincidente" in item["alerts"]
        for item in preview
    )
    assert employee > 0


def test_import_normalizes_datetime_values_without_seconds_and_preserves_original(
    tmp_path, database
):
    path = tmp_path / "marcaciones_sinteticas.csv"
    path.write_text(
        "codigo_trabajador,fecha,entrada,salida\n"
        "TEST-001,2026-11-18,2026-11-18 07:30,2026-11-18 17:00\n",
        encoding="utf-8",
    )
    service = AttendanceService(database)
    dataset = service.read_import_source(path)
    preview = service.preview_import(dataset, service.guess_mapping(dataset.headers))

    assert preview[0]["entry_time"] == "07:30"
    assert preview[0]["exit_time"] == "17:00"
    assert preview[0]["original_entry_time"] == "2026-11-18 07:30"
    assert preview[0]["original_exit_time"] == "2026-11-18 17:00"
    assert preview[0]["alerts"] == ["Código sin empleado asociado"]


def test_import_batches_distinguish_documentary_and_synthetic_sources(tmp_path, database):
    service = AttendanceService(database)
    classifications = (
        ("transcripcion_sintetica.csv", "2026-10-25", "transcripcion_documental"),
        ("datos_ficticios.csv", "2026-10-26", "datos_sinteticos"),
    )
    for filename, work_date, source_type in classifications:
        path = tmp_path / filename
        path.write_text(
            "codigo_trabajador,fecha,entrada,salida\n"
            f"DEMO-001,{work_date},08:00,17:00\n",
            encoding="utf-8",
        )
        dataset = service.read_import_source(path)
        result = service.import_reviewed(
            dataset,
            service.guess_mapping(dataset.headers),
            source_type,
        )
        assert result["imported"] == 1

    sources = database.fetch_all(
        "SELECT source_name, source_type FROM attendance_imports ORDER BY id"
    )
    assert sources == [
        {
            "source_name": "archivo.csv",
            "source_type": "transcripcion_documental",
        },
        {
            "source_name": "archivo.csv",
            "source_type": "datos_sinteticos",
        },
    ]


def test_import_excludes_contact_headers_and_rejects_sensitive_mapping(
    tmp_path, database, employee
):
    path = tmp_path / "archivo_con_datos_personales.csv"
    path.write_text(
        "Código interno,Nombre,Correo electrónico,Teléfono,Dirección,Salario,"
        "Fecha,Entrada,Salida\n"
        "TEST-001,Persona Ficticia,persona@example.test,3000000000,"
        "Dirección ficticia,999999,2026-10-25,08:00,17:00\n",
        encoding="utf-8",
    )
    service = AttendanceService(database)
    dataset = service.read_import_source(path)

    assert dataset.headers == ("Código interno", "Fecha", "Entrada", "Salida")
    assert "Persona Ficticia" not in repr(dataset.rows)
    assert "persona@example.test" not in repr(dataset.rows)
    assert "3000000000" not in repr(dataset.rows)
    assert "Dirección ficticia" not in repr(dataset.rows)
    assert "999999" not in repr(dataset.rows)

    unsafe_dataset = ImportDataset(
        path=path,
        headers=("Correo electrónico", "Fecha", "Entrada", "Salida"),
        rows=(
            ImportRow(
                row_number=2,
                values={
                    "Correo electrónico": "persona@example.test",
                    "Fecha": "2026-10-25",
                    "Entrada": "08:00",
                    "Salida": "17:00",
                },
                raw={},
            ),
        ),
        groups={},
        sheet_name="CSV",
    )
    with pytest.raises(ValueError, match="datos personales"):
        service.preview_import(
            unsafe_dataset,
            {
                "employee_code": "Correo electrónico",
                "work_date": "Fecha",
                "entry_time": "Entrada",
                "exit_time": "Salida",
            },
        )
    assert employee > 0


def test_xlsx_import_uses_the_selected_sheet(tmp_path, database, employee):
    from openpyxl import Workbook

    path = tmp_path / "libro_sintetico_varias_hojas.xlsx"
    workbook = Workbook()
    workbook.active.title = "Instrucciones"
    workbook.active.append(("No importar",))
    sheet = workbook.create_sheet("Marcaciones")
    sheet.append(("codigo_trabajador", "fecha", "entrada", "salida"))
    sheet.append(("TEST-001", "2026-10-25", "08:00", "17:00"))
    workbook.save(path)

    service = AttendanceService(database)

    assert service.available_sheets(path) == ("Instrucciones", "Marcaciones")
    dataset = service.read_import_source(path, "Marcaciones")
    preview = service.preview_import(dataset, service.guess_mapping(dataset.headers))
    assert dataset.sheet_name == "Marcaciones"
    assert len(preview) == 1
    assert preview[0]["employee_id"] == employee

    with pytest.raises(ValueError, match="hoja seleccionada no existe"):
        service.read_import_source(path, "Hoja inexistente")


def test_grouped_excel_report_requires_and_records_manual_employee_mapping(
    tmp_path, database, employee
):
    from openpyxl import Workbook

    path = tmp_path / "reporte_agrupado_sintetico.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Asistencia"
    sheet["D3"] = "Nombre: Persona Ficticia Uno"
    sheet.append([])
    sheet.append([])
    sheet.append([])
    sheet.append([])
    sheet.append([])
    sheet.append([])
    sheet.append([None, None, None, None, "Fecha", "Entrada 1", "Salida 1", "TOTAL"])
    sheet.append([None, None, None, None, "2026-10-25", "08:00", "17:00", 9])
    sheet.append([None, None, None, None, "TOTAL", None, None, 9])
    sheet["D12"] = "Nombre: Persona Ficticia Dos"
    sheet.append([])
    sheet.append([])
    sheet.append([None, None, None, None, "Fecha", "Entrada 1", "Salida 1", "TOTAL"])
    sheet.append([None, None, None, None, "2026-10-26", "08:00", "17:00", 9])
    workbook.save(path)

    service = AttendanceService(database)
    dataset = service.read_import_source(path, "Asistencia")
    mapping = service.guess_mapping(dataset.headers)

    assert dataset.grouped_report
    assert tuple(dataset.groups.values()) == (
        "Grupo de empleado 1",
        "Grupo de empleado 2",
    )
    assert "Persona Ficticia Uno" not in repr(dataset)
    assert "Persona Ficticia Dos" not in repr(dataset)
    assert mapping["employee_code"] == ""
    preview = service.preview_import(
        dataset, mapping, {str(dataset.rows[0].row_number - 1): "TEST-001"}
    )
    assert len(preview) == 2

    group_key = dataset.rows[0].group_key
    preview = service.preview_import(dataset, mapping, {group_key: "TEST-001"})
    assert "Persona Ficticia Uno" not in repr(preview)
    assert preview[0]["employee_id"] == employee
    assert preview[1]["employee_id"] is None
    assert "Código sin empleado asociado" in preview[1]["alerts"]
    result = service.import_reviewed(
        dataset,
        mapping,
        "no_verificada",
        {group_key: "TEST-001"},
    )
    assert result["imported"] == 2
    assert database.fetch_one(
        "SELECT COUNT(*) AS n FROM attendance WHERE import_batch_id = ? AND employee_id IS NULL",
        (result["batch_id"],),
    )["n"] == 1
    imported_rows = database.fetch_all(
        "SELECT raw_data FROM attendance WHERE import_batch_id = ?",
        (result["batch_id"],),
    )
    assert all(
        "Persona Ficticia" not in record["raw_data"]
        for record in imported_rows
    )


def test_import_excludes_personal_columns_from_preview_and_database(tmp_path, database):
    path = tmp_path / "asistencia_sintetica_con_identificadores.csv"
    path.write_text(
        "Código interno,Nombre del trabajador,ID personal,Cédula,"
        "Autorizado por,Aprobado por,Fecha,Entrada,Salida\n"
        "TEST-001,Persona Ficticia,ID-123456,123456789,"
        "Responsable Ficticio,Supervisor Ficticio,2026-10-25,08:00,17:00\n",
        encoding="utf-8",
    )
    service = AttendanceService(database)
    dataset = service.read_import_source(path)

    assert dataset.headers == (
        "Código interno",
        "Fecha",
        "Entrada",
        "Salida",
    )
    assert "Persona Ficticia" not in repr(dataset.rows)
    assert "ID-123456" not in repr(dataset.rows)
    assert "123456789" not in repr(dataset.rows)
    assert "Responsable Ficticio" not in repr(dataset.rows)
    assert "Supervisor Ficticio" not in repr(dataset.rows)

    mapping = service.guess_mapping(dataset.headers)
    preview = service.preview_import(dataset, mapping)
    assert "Persona Ficticia" not in repr(preview)
    assert "ID-123456" not in repr(preview)
    assert "123456789" not in repr(preview)
    assert "Responsable Ficticio" not in repr(preview)
    assert "Supervisor Ficticio" not in repr(preview)
    assert preview[0]["raw_data"]["Fecha"] == "2026-10-25"

    result = service.import_reviewed(dataset, mapping, "datos_sinteticos")
    stored = database.fetch_one(
        "SELECT raw_data FROM attendance WHERE import_batch_id = ?",
        (result["batch_id"],),
    )
    assert "Persona Ficticia" not in stored["raw_data"]
    assert "ID-123456" not in stored["raw_data"]
    assert "123456789" not in stored["raw_data"]
    assert "Responsable Ficticio" not in stored["raw_data"]
    assert "Supervisor Ficticio" not in stored["raw_data"]


def test_imports_fifty_synthetic_rows_without_personal_columns(
    tmp_path, database, employee
):
    path = tmp_path / "muestra_sintetica_50.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as source_file:
        writer = csv.writer(source_file)
        writer.writerow(
            ["Codigo interno", "Fecha", "Entrada", "Salida", "Nombre", "Documento"]
        )
        for index in range(50):
            work_date = date(2026, 10, 25) + timedelta(days=index)
            writer.writerow(
                [
                    "TEST-001",
                    work_date.isoformat(),
                    "08:00",
                    "17:00",
                    f"Persona Ficticia {index + 1:03d}",
                    f"ID-FICTICIO-{index + 1:03d}",
                ]
            )

    service = AttendanceService(database)
    dataset = service.read_import_source(path)
    mapping = service.guess_mapping(dataset.headers)
    preview = service.preview_import(dataset, mapping)

    assert len(dataset.rows) == 50
    assert len(preview) == 50
    assert all(not record["alerts"] for record in preview)
    assert "Persona Ficticia" not in repr(dataset.rows)
    assert "ID-FICTICIO" not in repr(preview)

    result = service.import_reviewed(dataset, mapping, "datos_sinteticos")
    stored = database.fetch_all(
        "SELECT raw_data FROM attendance WHERE import_batch_id = ?",
        (result["batch_id"],),
    )
    assert result["imported"] == 50
    assert result["invalid"] == 0
    assert result["duplicates"] == 0
    assert result["unmatched"] == 0
    assert len(stored) == 50
    assert all("Persona Ficticia" not in row["raw_data"] for row in stored)
    assert all("ID-FICTICIO" not in row["raw_data"] for row in stored)


def test_database_additive_migration_preserves_existing_rows(tmp_path):
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL, position TEXT NOT NULL DEFAULT '',
            department TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE attendance (
            id INTEGER PRIMARY KEY, employee_id INTEGER,
            employee_code TEXT NOT NULL DEFAULT '', work_date TEXT NOT NULL DEFAULT '',
            entry_time TEXT NOT NULL DEFAULT '', exit_time TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE permissions (
            id INTEGER PRIMARY KEY, employee_id INTEGER NOT NULL,
            requested_on TEXT NOT NULL, start_date TEXT NOT NULL,
            start_time TEXT NOT NULL, end_date TEXT NOT NULL,
            end_time TEXT NOT NULL, permission_type TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'Pendiente',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE overtime (
            id INTEGER PRIMARY KEY, employee_id INTEGER NOT NULL,
            work_date TEXT NOT NULL, start_time TEXT NOT NULL,
            end_time TEXT NOT NULL, hours REAL NOT NULL,
            shift_type TEXT NOT NULL, activity TEXT NOT NULL DEFAULT '',
            authorized INTEGER NOT NULL DEFAULT 0, notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO attendance (employee_code, work_date, entry_time, exit_time)
        VALUES ('LEGACY-001', '2026-10-25', '08:00', '17:00');
        """
    )
    connection.commit()
    connection.close()

    migrated = Database(path)
    columns = {
        table: {
            row["name"]
            for row in migrated.connection.execute(f"PRAGMA table_info({table})")
        }
        for table in ("attendance", "permissions", "overtime")
    }
    existing = migrated.fetch_one(
        "SELECT employee_code, work_date, entry_time, exit_time FROM attendance WHERE id = ?",
        (1,),
    )
    assert {"import_batch_id", "source_row", "raw_data"} <= columns["attendance"]
    assert {
        "remunerated",
        "duration_hours",
        "duration_days",
        "reason",
        "applicant_signed",
        "manager_approval_recorded",
    } <= columns["permissions"]
    assert {
        "period",
        "authorized_by",
        "approved_by",
        "total_hours",
        "reported_surcharge",
        "sunday_holiday",
        "lunch_hour_worked",
    } <= columns["overtime"]
    assert existing == {
        "employee_code": "LEGACY-001",
        "work_date": "2026-10-25",
        "entry_time": "08:00",
        "exit_time": "17:00",
    }
    migrated.close()


def test_excel_import_normalizes_dates_and_times(tmp_path, database, employee):
    from openpyxl import Workbook

    path = tmp_path / "asistencia_sintetica.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(("codigo_trabajador", "fecha", "entrada", "salida", "fuente"))
    sheet.append(
        (
            "TEST-001",
            "2026-10-25",
            "08:00",
            "17:00",
            "registro sintético",
        )
    )
    sheet.append(("NO-REGISTRADO", "fecha inválida", "8am", None, None))
    workbook.save(path)

    service = AttendanceService(database)
    assert service.import_excel(path) == 2
    results = service.list()
    known = next(record for record in results if record["employee_code"] == "TEST-001")
    unknown = next(record for record in results if record["employee_code"] == "NO-REGISTRADO")
    assert known["employee_id"] == employee
    assert known["work_date"] == "2026-10-25"
    assert known["entry_time"] == "08:00"
    assert unknown["source"] == "Sin verificar"
    assert any("Fecha no reconocida" in alert for alert in unknown["alerts"])


def test_invalid_excel_file_is_rejected_without_records(tmp_path, database):
    path = tmp_path / "no_es_excel.xlsx"
    path.write_text("contenido ficticio", encoding="utf-8")

    with pytest.raises(ValueError, match="no es un Excel"):
        AttendanceService(database).import_excel(path)
    assert database.fetch_one("SELECT COUNT(*) AS n FROM attendance")["n"] == 0


def test_permission_create_update_and_invalid_interval(database, employee):
    service = PermissionService(database)
    permission_id = service.save(
        employee, "2026-10-20", "2026-10-25", "09:00",
        "2026-10-25", "11:00", "Cita personal", "Prueba sintética",
        remunerated="No remunerado", duration_hours=2,
        applicant_signed=True, manager_approval_recorded=True,
        duration_days=0.5, reason="Motivo ficticio",
    )
    created = service.list()[0]
    assert created["applicant_signed"] == 1
    assert created["manager_approval_recorded"] == 1
    service.save(
        employee, "2026-10-20", "2026-10-25", "09:00",
        "2026-10-25", "11:00", "Cita personal", "Actualizada", "Aprobado",
        permission_id, remunerated="Remunerado", duration_hours="1.5",
        duration_days="1.5", reason="Motivo actualizado",
    )
    results = service.list(employee_id=employee, start_date="2026-10-25", end_date="2026-10-25")
    assert len(results) == 1
    assert results[0]["status"] == "Aprobado"
    assert results[0]["notes"] == "Actualizada"
    assert results[0]["remunerated"] == "Remunerado"
    assert results[0]["duration_hours"] == 1.5
    assert results[0]["duration_days"] == 1.5
    assert results[0]["reason"] == "Motivo actualizado"
    assert results[0]["applicant_signed"] == 0
    assert results[0]["manager_approval_recorded"] == 0

    with pytest.raises(ValueError, match="posterior"):
        service.save(
            employee, "2026-10-20", "2026-10-25", "11:00",
            "2026-10-25", "09:00", "Cita personal",
        )
    with pytest.raises(ValueError, match="duración reportada"):
        service.save(
            employee, "2026-10-20", "2026-10-25", "09:00",
            "2026-10-25", "11:00", "Cita personal",
            duration_hours="no numérica",
        )
    with pytest.raises(ValueError, match="días"):
        service.save(
            employee, "2026-10-20", "2026-10-25", "09:00",
            "2026-10-25", "11:00", "Cita personal",
            duration_days="NaN",
        )


def test_permission_requires_registered_employee(database):
    with pytest.raises(sqlite3.IntegrityError):
        PermissionService(database).save(
            999, "2026-10-20", "2026-10-25", "09:00",
            "2026-10-25", "11:00", "Cita",
        )


def test_permission_delete_removes_selected_request(database, employee):
    service = PermissionService(database)
    permission_id = service.save(
        employee,
        "2026-10-20",
        "2026-10-25",
        "09:00",
        "2026-10-25",
        "11:00",
        "Cita personal",
    )

    service.delete(permission_id)

    assert service.list() == []
    with pytest.raises(ValueError, match="ya no existe"):
        service.delete(permission_id)


def test_permission_period_filter_includes_overlapping_requests(database, employee):
    service = PermissionService(database)
    service.save(
        employee, "2026-10-20", "2026-10-24", "09:00",
        "2026-10-26", "11:00", "Permiso que cruza el filtro",
    )

    results = service.list(start_date="2026-10-25", end_date="2026-10-25")

    assert len(results) == 1


def test_overtime_create_update_and_reject_invalid_hours(database, employee):
    service = OvertimeService(database)
    overtime_id = service.save(
        employee, "2026-10-25", "18:00", "20:00", "2",
        "Nocturna", "Mantenimiento", True, "Prueba sintética",
        period="Octubre 2026", authorized_by="Responsable ficticio",
        approved_by="Supervisor ficticio", total_hours="9.5",
        lunch_hour_worked=True, sunday_holiday="Dato F-074: domingos y festivos",
        reported_surcharge="Dato reportado sin cálculo",
    )
    created = service.list()[0]
    assert created["total_hours"] == 9.5
    assert created["lunch_hour_worked"] == 1
    assert created["sunday_holiday"] == "Dato F-074: domingos y festivos"
    assert created["reported_surcharge"] == "Dato reportado sin cálculo"
    service.save(
        employee, "2026-10-25", "18:00", "20:00", "2.5",
        "Nocturna", "Mantenimiento", False, "Revisión", overtime_id,
        period="Periodo actualizado", authorized_by="Autorizador ficticio",
        approved_by="Aprobador ficticio", total_hours="8",
        lunch_hour_worked=None, sunday_holiday="Actualizado",
        reported_surcharge="Recargo informado",
    )
    results = service.list(employee_id=employee, start_date="2026-10-25", end_date="2026-10-25")
    assert len(results) == 1
    assert results[0]["hours"] == 2.5
    assert results[0]["authorized"] == 0
    assert results[0]["period"] == "Periodo actualizado"
    assert results[0]["authorized_by"] == "Autorizador ficticio"
    assert results[0]["approved_by"] == "Aprobador ficticio"
    assert results[0]["total_hours"] == 8
    assert results[0]["lunch_hour_worked"] is None
    assert results[0]["sunday_holiday"] == "Actualizado"
    assert results[0]["reported_surcharge"] == "Recargo informado"

    with pytest.raises(ValueError, match="hasta 24"):
        service.save(
            employee, "2026-10-25", "18:00", "20:00", "25",
            "Nocturna",
        )
    with pytest.raises(ValueError, match="total de horas"):
        service.save(
            employee, "2026-10-25", "18:00", "20:00", "2",
            "Nocturna", total_hours="sin dato numérico",
        )


def test_overtime_rejects_equal_start_and_end(database, employee):
    with pytest.raises(ValueError, match="no pueden ser iguales"):
        OvertimeService(database).save(
            employee, "2026-10-25", "18:00", "18:00", "1",
            "Diurna",
        )


def test_overtime_delete_removes_selected_record(database, employee):
    service = OvertimeService(database)
    overtime_id = service.save(
        employee, "2026-10-25", "18:00", "20:00", "2", "Nocturna"
    )

    service.delete(overtime_id)

    assert service.list() == []
    with pytest.raises(ValueError, match="ya no existe"):
        service.delete(overtime_id)


def test_validators_reject_impossible_dates_and_times():
    assert valid_date("2026-10-25")
    assert not valid_date("2026-02-30")
    assert valid_time("23:59")
    assert not valid_time("24:00")
    assert attendance_alerts(
        {"employee_id": 1, "work_date": "2026-10-25", "entry_time": "", "exit_time": ""}
    )


def test_csv_export_contains_filtered_records_and_observations(tmp_path, database, employee):
    attendance = AttendanceService(database)
    attendance.add("TEST-001", "2026-10-25", "08:00", "")
    records = attendance.list(employee_id=employee)
    path = tmp_path / "informe.csv"

    attendance.export_csv(path, records)

    with path.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 1
    assert rows[0]["codigo_trabajador"] == "TEST-001"
    assert "Falta la hora de salida" in rows[0]["observaciones"]
    assert "nombre_empleado" not in rows[0]
    assert "fuente" not in rows[0]
    assert "Persona Ficticia" not in path.read_text(encoding="utf-8-sig")


@pytest.mark.parametrize(
    "kind,forbidden_fields",
    [
        ("Asistencia", {"employee_name", "source"}),
        ("Permisos", {"employee_name", "reason", "notes"}),
        (
            "Horas extra",
            {
                "employee_name",
                "activity",
                "authorized_by",
                "approved_by",
                "notes",
                "reported_surcharge",
            },
        ),
        ("Empleados", {"name", "position", "department"}),
    ],
)
def test_legacy_report_exports_omit_names_and_free_text(kind, forbidden_fields):
    fake_window = SimpleNamespace(report_type=SimpleNamespace(get=lambda: kind))

    fields, headers = MainWindow.report_export_columns.fget(fake_window)

    assert len(fields) == len(headers)
    assert forbidden_fields.isdisjoint(fields)


def test_employee_combo_displays_names_and_keeps_code_mapping():
    employee = {"code": "202601", "name": "Persona Sintética Uno"}
    label = MainWindow._employee_option(employee)

    class FakeCombo:
        _employee_code_by_label = {label: employee["code"]}

        def __init__(self):
            self.value = label

        def get(self):
            return self.value

        def set(self, value):
            self.value = value

    combo = FakeCombo()
    assert label == "202601 | Persona Sintética Uno"
    assert MainWindow._combo_code(combo) == "202601"

    MainWindow._set_combo_code(combo, "202601")
    assert combo.get() == label


def test_employee_combo_id_resolves_display_label_and_requires_active_employee(
    database,
):
    employee_id = EmployeeService(database).save(
        "TEST-COMBO-001", "Persona Sintética", "Auxiliar", "Área de prueba"
    )
    label = "TEST-COMBO-001 | Persona Sintética"
    combo = SimpleNamespace(
        get=lambda: label,
        _employee_code_by_label={label: "TEST-COMBO-001"},
    )
    window = MainWindow.__new__(MainWindow)
    window.database = database

    assert window._combo_id(combo) == employee_id

    EmployeeService(database).set_active(employee_id, False)
    assert window._combo_id(combo) is None


def test_permission_form_saves_selected_active_employee(monkeypatch):
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"Tk display is unavailable: {error}")

    database = Database(":memory:")
    employee_id = EmployeeService(database).save(
        "TEST-PERM-001", "Persona Sintética", "Auxiliar", "Área de prueba"
    )
    app = MainWindow(root, database)
    warnings = []
    errors = []
    monkeypatch.setattr(
        "views.ventana_principal.messagebox.showwarning",
        lambda title, message, **kwargs: warnings.append(message),
    )
    monkeypatch.setattr(
        "views.ventana_principal.messagebox.showerror",
        lambda title, message, **kwargs: errors.append(message),
    )
    app._notify = lambda _message: None
    try:
        app.show_page("Permisos")
        root.update()
        app._set_combo_code(app.perm_employee, "TEST-PERM-001")
        today = date.today().isoformat()
        for field, value in (
            (app.perm_requested, today),
            (app.perm_start_date, today),
            (app.perm_start_time, "09:00"),
            (app.perm_end_date, today),
            (app.perm_end_time, "10:00"),
            (app.perm_reason, "Prueba sintética"),
        ):
            app._set_entry(field, value)
        app.perm_type.set("Personal")
        app.perm_status.set("Pendiente")
        app.perm_remunerated.set("No remunerado")

        app._save_permission()

        records = app.permissions.list(employee_id=employee_id)
        assert len(records) == 1
        assert records[0]["reason"] == "Prueba sintética"
        assert not warnings
        assert not errors
    finally:
        app.close()


@pytest.mark.parametrize(
    "delta,expected",
    [(120, -1), (-120, 1), (60, -1), (-60, 1)],
)
def test_mousewheel_delta_maps_to_scroll_units(delta, expected):
    assert MainWindow._wheel_steps(SimpleNamespace(delta=delta)) == expected


def test_mousewheel_scrolls_the_page_and_table_independently():
    class FakeScrollable:
        def __init__(self):
            self.vertical_calls = []
            self.horizontal_calls = []

        def yview_scroll(self, steps, units):
            self.vertical_calls.append((steps, units))

        def xview_scroll(self, steps, units):
            self.horizontal_calls.append((steps, units))

    page = FakeScrollable()
    assert MainWindow._scroll_page_content(
        SimpleNamespace(page_canvas=page), SimpleNamespace(delta=-120)
    ) == "break"
    assert page.vertical_calls == [(1, "units")]

    table = FakeScrollable()
    event = SimpleNamespace(delta=120, widget=table)
    assert MainWindow._scroll_table(SimpleNamespace(), event) == "break"
    assert MainWindow._scroll_table_horizontally(
        SimpleNamespace(), event
    ) == "break"
    assert table.vertical_calls == [(-1, "units")]
    assert table.horizontal_calls == [(-1, "units")]


def test_excel_export_creates_workbook(tmp_path, database):
    path = tmp_path / "informe.xlsx"
    ReportService(database).export_excel(
        path, [{"Código": "DEMO-001", "Total": 3}], ["Código", "Total"]
    )

    from openpyxl import load_workbook

    sheet = load_workbook(path, read_only=True).active
    assert list(sheet.values) == [("Código", "Total"), ("DEMO-001", 3)]


def test_summary_counts_employees_and_records(database, employee):
    assert employee > 0
    AttendanceService(database).add("TEST-001", "2026-10-25", "08:00", "17:00")

    summary = ReportService(database).summary()

    assert summary == {
        "employees": 1,
        "attendance": 1,
        "permissions_pending": 0,
        "overtime": 0,
    }


def test_independent_synthetic_dataset_exercises_all_modules(database):
    fixture_path = Path(__file__).parent / "fixtures" / "datos_ficticios_proyecto.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert payload["classification"].startswith("DATOS SINTÉTICOS DE PRUEBA")

    employee_service = EmployeeService(database)
    employee_ids = {
        item["code"]: employee_service.save(
            item["code"],
            item["name"],
            item["position"],
            item["department"],
        )
        for item in payload["employees"]
    }
    attendance_service = AttendanceService(database)
    for item in payload["attendance"]:
        attendance_service.add(**item, source="Datos sintéticos de prueba")

    permission_service = PermissionService(database)
    for item in payload["permissions"]:
        permission_service.save(employee_ids["DEMO-001"], **item)

    overtime_service = OvertimeService(database)
    for item in payload["overtime"]:
        overtime_service.save(employee_ids["DEMO-001"], **item)

    assert len(employee_service.list()) == 1
    assert len(attendance_service.list()) == 1
    assert len(permission_service.list()) == 1
    assert len(overtime_service.list()) == 1
    assert attendance_service.list()[0]["source"] == "Datos sintéticos de prueba"
    assert permission_service.list()[0]["remunerated"] == "No remunerado"
    assert overtime_service.list()[0]["period"] == "Periodo ficticio octubre 2026"
    assert overtime_service.list()[0]["total_hours"] == 9
    assert overtime_service.list()[0]["lunch_hour_worked"] == 0


def test_employee_dialog_opens_centered_and_saves_from_ui():
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"Tk display is unavailable: {error}")

    database = Database(":memory:")
    app = MainWindow(root, database)
    try:
        root.update()
        app.show_page("Empleados")
        app._employee_dialog()
        root.update()

        dialog = next(
            child
            for child in root.winfo_children()
            if isinstance(child, tk.Toplevel)
        )
        root_center = root.winfo_rootx() + root.winfo_width() / 2
        dialog_center = dialog.winfo_rootx() + dialog.winfo_width() / 2
        assert abs(root_center - dialog_center) <= 10

        fields = []
        for cell in dialog.winfo_children():
            entry = next(
                (
                    child
                    for child in cell.winfo_children()
                    if isinstance(child, ttk.Entry)
                ),
                None,
            )
            if entry is not None:
                grid_info = cell.grid_info()
                fields.append(
                    (int(grid_info["row"]), int(grid_info["column"]), entry)
                )
        fields.sort(key=lambda item: (item[0], item[1]))
        for (_, _, entry), value in zip(
            fields,
            ("TEST-001", "Persona Ficticia", "Auxiliar", "Obra de prueba"),
        ):
            entry.insert(0, value)

        save_button = next(
            child
            for child in dialog.winfo_children()
            if isinstance(child, ttk.Button)
        )
        save_button.invoke()
        root.update()

        assert app.employees.list()[0]["code"] == "TEST-001"
    finally:
        app.close()


def test_ui_deletes_records_and_preserves_employee_history(monkeypatch):
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"Tk display is unavailable: {error}")

    database = Database(":memory:")
    app = MainWindow(root, database)
    employee_service = EmployeeService(database)
    attendance_service = AttendanceService(database)
    permission_service = PermissionService(database)
    overtime_service = OvertimeService(database)
    warnings: list[str] = []
    monkeypatch.setattr(
        "views.ventana_principal.messagebox.askyesno",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "views.ventana_principal.messagebox.showwarning",
        lambda title, message, **kwargs: warnings.append(message),
    )
    monkeypatch.setattr(
        "views.ventana_principal.messagebox.showerror",
        lambda title, message, **kwargs: pytest.fail(message),
    )
    try:
        root.update()
        employee_id = employee_service.save(
            "TEST-001", "Persona Ficticia", "Auxiliar", "Obra de prueba"
        )
        today = "2026-11-12"
        attendance_service.add("TEST-001", today, "08:00", "17:00")
        permission_service.save(
            employee_id,
            today,
            today,
            "09:00",
            today,
            "10:00",
            "Personal",
        )
        overtime_service.save(
            employee_id, today, "18:00", "20:00", 2, "Nocturna"
        )

        app.show_page("Empleados")
        root.update()
        employee_row = app.employee_tree.get_children()[0]
        app.employee_tree.selection_set(employee_row)
        app._delete_employee()
        assert employee_service.get(employee_id) is not None
        assert warnings and "Desactívelo" in warnings[-1]

        app.show_page("Asistencia")
        root.update()
        attendance_row = app.attendance_tree.get_children()[0]
        app.attendance_tree.selection_set(attendance_row)
        app._delete_attendance()
        assert attendance_service.list() == []

        app.show_page("Permisos")
        root.update()
        permission_row = app.permission_tree.get_children()[0]
        app.permission_tree.selection_set(permission_row)
        app._delete_permission()
        assert permission_service.list() == []

        app.show_page("Horas extras")
        root.update()
        overtime_row = app.overtime_tree.get_children()[0]
        app.overtime_tree.selection_set(overtime_row)
        app._delete_overtime()
        assert overtime_service.list() == []

        app.show_page("Empleados")
        root.update()
        employee_row = app.employee_tree.get_children()[0]
        app.employee_tree.selection_set(employee_row)
        app._delete_employee()
        assert employee_service.get(employee_id) is None
    finally:
        app.close()


def test_ui_navigation_and_dashboard_layout_at_supported_sizes():
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"Tk display is unavailable: {error}")

    app = MainWindow(root, Database(":memory:"))
    try:
        for page in app.PAGES:
            app.show_page(page)
            root.update()
            assert app.page_title.cget("text") == page

        app.show_page("Panel principal")
        root.geometry("1160x700")
        root.update()
        summary = app.reports.summary()
        assert [
            card.winfo_children()[0].value_label.cget("text")
            for card in app.dashboard_cards
        ] == [
            str(summary["employees"]),
            str(summary["attendance"]),
            str(summary["permissions_pending"]),
            str(summary["overtime"]),
            str(sum(bool(record["alerts"]) for record in app.attendance.list())),
        ]
        assert app.dashboard_quick_actions.winfo_ismapped()
        assert app.hero_canvas.find_withtag("dashboard-art")
        quick_actions_height = app.dashboard_quick_actions.winfo_height()

        root.geometry("1366x768")
        root.update()
        assert app.dashboard_quick_actions.winfo_ismapped()
        assert app.dashboard_quick_actions.winfo_height() == quick_actions_height
        assert app.hero_canvas.find_withtag("dashboard-art")
    finally:
        app.close()


def test_data_page_and_table_can_scroll_in_both_directions():
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"Tk display is unavailable: {error}")

    app = MainWindow(root, Database(":memory:"))
    try:
        root.minsize(720, 400)
        root.geometry("1000x700")
        app.show_page("Asistencia")
        root.update()

        region = app.page_canvas.bbox("all")
        assert region is not None
        assert region[3] > app.page_canvas.winfo_height()
        assert app.page_canvas.cget("yscrollcommand")

        tree = app.attendance_tree
        assert int(tree.cget("height")) == 12
        assert tree.cget("yscrollcommand")
        assert tree.cget("xscrollcommand")
        for index in range(30):
            tree.insert("", "end", values=tuple(f"fila-{index}" for _ in range(10)))
        root.update()

        vertical_before = tree.yview()[0]
        app._scroll_table(SimpleNamespace(delta=-120, widget=tree))
        assert tree.yview()[0] > vertical_before

        horizontal_before = tree.xview()[0]
        app._scroll_table_horizontally(
            SimpleNamespace(delta=-120, widget=tree)
        )
        assert tree.xview()[0] > horizontal_before
    finally:
        app.close()


def test_desktop_actions_reflow_below_filters_in_narrow_windows():
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"Tk display is unavailable: {error}")

    app = MainWindow(root, Database(":memory:"))
    try:
        root.minsize(720, 400)
        root.geometry("1000x700")
        for page in ("Asistencia", "Informes y consultas", "Empleados"):
            app.show_page(page)
            root.update()

            if page == "Asistencia":
                assert app.attendance_form_actions.grid_info()["row"] == 3
                assert app.attendance_filter_actions.grid_info()["row"] == 1
            elif page == "Informes y consultas":
                assert app.report_actions.grid_info()["row"] == 2
            else:
                assert app.employee_actions.winfo_ismapped()
    finally:
        app.close()


def test_icon_action_button_hover_does_not_change_visual_state_or_geometry():
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"Tk display is unavailable: {error}")

    clicked: list[bool] = []
    button = IconActionButton(
        root, "Exportar CSV", "file-down", lambda: clicked.append(True)
    )
    button.pack(padx=20, pady=20)
    try:
        root.update()
        original_geometry = (
            button.winfo_rootx(),
            button.winfo_rooty(),
            button.winfo_width(),
            button.winfo_height(),
        )

        original_colors = (
            button.cget("background"),
            button.text.cget("background"),
            button.icon.cget("background"),
        )
        button.event_generate("<Enter>")
        button.event_generate("<Leave>")
        root.update()
        assert (
            button.cget("background"),
            button.text.cget("background"),
            button.icon.cget("background"),
        ) == original_colors
        assert (
            button.winfo_rootx(),
            button.winfo_rooty(),
            button.winfo_width(),
            button.winfo_height(),
        ) == original_geometry

        button._on_click(None)
        assert clicked == [True]
    finally:
        root.destroy()


def test_brand_mark_and_navigation_icons_render_without_assets():
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"Tk display is unavailable: {error}")

    try:
        brand = tk.Canvas(root, width=42, height=42)
        draw_brand_mark(brand)
        assert len(brand.find_all()) >= 5

        canvas = tk.Canvas(root, width=20, height=20)
        for icon in ("dashboard", "users", "calendar-check", "clock", "shield", "chart"):
            draw_icon(canvas, icon, "#5965D8")
            assert canvas.find_all(), f"El icono {icon} no dibujó elementos."
    finally:
        root.destroy()


def test_sidebar_navigation_stays_clickable_and_scrolls_in_short_window():
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"Tk display is unavailable: {error}")

    database = Database(":memory:")
    app = MainWindow(root, database)
    try:
        root.minsize(720, 400)
        root.geometry("1000x520")
        root.update()

        item = app.nav_buttons["Empleados"]
        original_geometry = (
            item.winfo_rootx(),
            item.winfo_rooty(),
            item.winfo_width(),
            item.winfo_height(),
        )
        item.event_generate("<Enter>")
        item.event_generate("<Leave>")
        root.update()
        assert (
            item.winfo_rootx(),
            item.winfo_rooty(),
            item.winfo_width(),
            item.winfo_height(),
        ) == original_geometry

        item.text.event_generate("<Button-1>", x=5, y=5)
        root.update()
        assert app.current_page == "Empleados"

        scroll_region = app.nav_canvas.bbox("all")
        assert scroll_region is not None
        assert scroll_region[3] > app.nav_canvas.winfo_height()
        app.nav_canvas.yview_moveto(1)
        root.update()
        last_item = app.nav_buttons["Informes y consultas"]
        canvas_top = app.nav_canvas.winfo_rooty()
        canvas_bottom = canvas_top + app.nav_canvas.winfo_height()
        assert last_item.winfo_rooty() >= canvas_top
        assert last_item.winfo_rooty() + last_item.winfo_height() <= canvas_bottom
    finally:
        app.close()


def test_report_export_buttons_keep_position_and_write_files(tmp_path, monkeypatch):
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"Tk display is unavailable: {error}")

    database = Database(":memory:")
    app = MainWindow(root, database)
    csv_path = tmp_path / "reporte.csv"
    excel_path = tmp_path / "reporte.xlsx"
    save_paths = iter((csv_path, excel_path))
    monkeypatch.setattr(
        "views.ventana_principal.filedialog.asksaveasfilename",
        lambda *args, **kwargs: str(next(save_paths)),
    )
    try:
        EmployeeService(database).save(
            "TEST-001", "Persona Ficticia", "Auxiliar", "Obra de prueba"
        )
        AttendanceService(database).add(
            "TEST-001", "2026-11-12", "08:00", "17:00"
        )
        app.show_page("Informes y consultas")
        root.update()

        def find_export_button(widget, label):
            if (
                isinstance(widget, IconActionButton)
                and widget.text.cget("text") == label
            ):
                return widget
            for child in widget.winfo_children():
                match = find_export_button(child, label)
                if match is not None:
                    return match
            return None

        for label, destination in (("CSV", csv_path), ("Excel", excel_path)):
            button = find_export_button(app.page_content, label)
            assert button is not None
            geometry = (
                button.winfo_rootx(),
                button.winfo_rooty(),
                button.winfo_width(),
                button.winfo_height(),
            )
            colors = (
                button.cget("background"),
                button.text.cget("background"),
                button.icon.cget("background"),
            )
            button.event_generate("<Enter>")
            button.event_generate("<Leave>")
            root.update()
            assert (
                button.cget("background"),
                button.text.cget("background"),
                button.icon.cget("background"),
            ) == colors
            button._on_click(None)
            root.update()
            assert destination.is_file()
            assert (
                button.winfo_rootx(),
                button.winfo_rooty(),
                button.winfo_width(),
                button.winfo_height(),
            ) == geometry
    finally:
        app.close()
