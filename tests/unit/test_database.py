"""Проверки выбора источника данных и локальной SQLite-схемы."""

from __future__ import annotations

from pathlib import Path

import pytest

from fastapi_template.configs.config import DatabaseSettings
from fastapi_template.db.database import (
    initialize_local_database,
    list_local_tables,
    resolve_database_target,
)

ROOT = Path(__file__).resolve().parents[2]


def test_local_database_is_created_from_idempotent_schema_template(tmp_path: Path) -> None:
    """Локальный режим должен создать SQLite-файл и таблицы из SQL-шаблона дважды без ошибки."""

    target = resolve_database_target(
        DatabaseSettings(), local_development=True, local_services_dir=tmp_path
    )
    schema_path = ROOT / "local_services" / "schema.sql"

    assert list_local_tables(target) == set()
    initialize_local_database(target, schema_path=schema_path)
    initialize_local_database(target, schema_path=schema_path)

    assert target.source == "local"
    assert target.local_path == tmp_path / "local.sqlite3"
    assert target.local_path.is_file()
    assert {"schema_versions", "example_records"} <= list_local_tables(target)


def test_external_database_target_uses_configured_url_without_creating_local_file(
    tmp_path: Path,
) -> None:
    """Отключение локального режима должно выбрать URL YAML-конфигурации без SQLite-файла."""

    external_url = "postgresql+psycopg://app:secret@db.example.test:5432/app"
    target = resolve_database_target(
        DatabaseSettings(url=external_url),
        local_development=False,
        local_services_dir=tmp_path,
    )

    assert target.source == "external"
    assert target.url == external_url
    assert target.local_path is None
    assert not any(tmp_path.iterdir())


def test_local_management_rejects_external_database_target(tmp_path: Path) -> None:
    """Шаблон локальных таблиц не должен по ошибке применяться к внешнему источнику."""

    target = resolve_database_target(
        DatabaseSettings(url="postgresql://db.example.test/app"),
        local_development=False,
        local_services_dir=tmp_path,
    )

    with pytest.raises(ValueError, match="локальной"):
        initialize_local_database(target)
    with pytest.raises(ValueError, match="локальной"):
        list_local_tables(target)
