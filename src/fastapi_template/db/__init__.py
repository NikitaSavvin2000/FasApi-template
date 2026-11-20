"""Выбор БД и инфраструктура хранения данных."""

from .database import DatabaseTarget, initialize_local_database, resolve_database_target

__all__ = ["DatabaseTarget", "initialize_local_database", "resolve_database_target"]
