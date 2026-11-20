"""Выбор БД и создание локального SQLite-хранилища из SQL-шаблона."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fastapi_template.configs.config import DatabaseSettings

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_LOCAL_SERVICES_DIR = _PROJECT_ROOT / "local_services"
_DATABASE_FILENAME = "local.sqlite3"
_SCHEMA_FILENAME = "schema.sql"


@dataclass(frozen=True, slots=True)
class DatabaseTarget:
    """Описывает выбранный источник данных без открытия соединения при импорте."""

    source: Literal["local", "external"]
    url: str
    local_path: Path | None = None


def resolve_database_target(
    settings: DatabaseSettings,
    *,
    local_development: bool,
    local_services_dir: Path | None = None,
) -> DatabaseTarget:
    """Выбирает локальный SQLite или внешний URL согласно валидированным настройкам."""

    if local_development:
        services_dir = (local_services_dir or _LOCAL_SERVICES_DIR).resolve()
        database_path = services_dir / _DATABASE_FILENAME
        return DatabaseTarget(
            source="local",
            url=f"sqlite:///{database_path.as_posix()}",
            local_path=database_path,
        )
    if settings.url is None:
        raise ValueError("Для внешней БД требуется database.url")
    return DatabaseTarget(source="external", url=settings.url)


def initialize_local_database(target: DatabaseTarget, *, schema_path: Path | None = None) -> None:
    """Создаёт локальный SQLite-файл и идемпотентно применяет SQL-шаблон таблиц."""

    if target.source != "local" or target.local_path is None:
        raise ValueError("Инициализировать таблицы можно только для локальной SQLite БД")
    template_path = schema_path or _LOCAL_SERVICES_DIR / _SCHEMA_FILENAME
    if not template_path.is_file():
        raise RuntimeError(f"Не найден SQL-шаблон локальной БД: {template_path}")
    target.local_path.parent.mkdir(parents=True, exist_ok=True)
    schema = template_path.read_text(encoding="utf-8")
    with sqlite3.connect(target.local_path) as connection:
        connection.executescript(schema)


def list_local_tables(target: DatabaseTarget) -> set[str]:
    """Возвращает имена пользовательских таблиц локальной SQLite БД для управления ею."""

    if target.source != "local" or target.local_path is None:
        raise ValueError("Просматривать таблицы можно только в локальной SQLite БД")
    if not target.local_path.is_file():
        return set()
    with sqlite3.connect(target.local_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    return {str(row[0]) for row in rows}
