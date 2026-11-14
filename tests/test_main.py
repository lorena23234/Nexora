from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import main


@pytest.mark.parametrize(
    ("configured_path", "expected_path"),
    [
        (None, main.DATABASE_PATH),
        ("custom.sqlite", Path("custom.sqlite")),
        (":memory:", ":memory:"),
    ],
)
def test_desktop_entry_uses_only_configured_database(
    monkeypatch, tmp_path, configured_path, expected_path
):
    state = {}
    root = SimpleNamespace(mainloop=lambda: state.update(mainloop=True))

    class FakeDatabase:
        def __init__(self, path):
            state["path"] = path

    monkeypatch.setattr(main.tk, "Tk", lambda: root)
    monkeypatch.setattr(main, "Database", FakeDatabase)
    monkeypatch.setattr(
        main,
        "MainWindow",
        lambda app_root, database: state.update(root=app_root, database=database),
    )
    if configured_path is None:
        monkeypatch.delenv("NEXORA_HR_DB_PATH", raising=False)
    elif configured_path == "custom.sqlite":
        monkeypatch.setenv(
            "NEXORA_HR_DB_PATH", str(tmp_path / configured_path)
        )
        expected_path = tmp_path / configured_path
    else:
        monkeypatch.setenv("NEXORA_HR_DB_PATH", configured_path)

    main.main()

    assert state["path"] == expected_path
    assert state["root"] is root
    assert state["mainloop"] is True
