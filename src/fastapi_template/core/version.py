"""Получение версии установленного пакета и публичного префикса API."""

from __future__ import annotations

import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def get_project_version() -> str:
    """Читает версию из pyproject.toml или из метаданных установленного пакета."""

    project_file = Path(__file__).resolve().parents[3] / "pyproject.toml"
    if project_file.is_file():
        with project_file.open("rb") as file:
            project = tomllib.load(file)["project"]
        return str(project["version"])
    try:
        return version("fastapi-template")
    except PackageNotFoundError:
        raise RuntimeError("Не удалось определить версию пакета fastapi-template") from None


def get_api_prefix() -> str:
    """Строит URL-префикс главной версии API из major-версии проекта."""

    major = get_project_version().split(".", maxsplit=1)[0]
    if not major.isdecimal() or int(major) < 1:
        raise RuntimeError("Версия проекта должна начинаться с положительного major-номера")
    return f"/v{major}"


PROJECT_VERSION = get_project_version()
API_PREFIX = get_api_prefix()
# Поддерживаемые HTTP-версии: первая выводится из версии проекта, следующие
# добавляются только вместе с отдельным router и документацией.
API_PREFIXES = (API_PREFIX, "/v2")
