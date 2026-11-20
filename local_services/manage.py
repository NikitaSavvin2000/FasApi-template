"""Управление локальной SQLite БД без запуска HTTP-сервиса."""

from __future__ import annotations

import argparse

from fastapi_template.configs.config import DatabaseSettings
from fastapi_template.db.database import (
    initialize_local_database,
    list_local_tables,
    resolve_database_target,
)


def _parse_args() -> argparse.Namespace:
    """Читает безопасную явную команду управления локальной БД."""

    parser = argparse.ArgumentParser(description="Управление local_services/local.sqlite3")
    parser.add_argument("command", choices=("init", "reset", "status"))
    return parser.parse_args()


def main() -> None:
    """Инициализирует, сбрасывает или показывает таблицы локальной БД."""

    command = _parse_args().command
    target = resolve_database_target(DatabaseSettings(), local_development=True)
    if target.local_path is None:
        raise RuntimeError("Команда управления требует локальную SQLite БД")
    if command == "reset" and target.local_path.exists():
        target.local_path.unlink()
    if command in {"init", "reset"}:
        initialize_local_database(target)
    print("\n".join(sorted(list_local_tables(target))) or "База данных ещё не создана")


if __name__ == "__main__":
    main()
