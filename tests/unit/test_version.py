"""Проверки связи версии пакета с URL-префиксом API."""

from __future__ import annotations

from fastapi_template.core import version as project_version


def test_api_prefix_uses_major_version_from_pyproject() -> None:
    """Публичный префикс обязан быть производным от major-версии pyproject.toml."""

    assert (
        project_version.get_api_prefix()
        == f"/v{project_version.get_project_version().split('.')[0]}"
    )


def test_project_version_uses_installed_metadata_without_source_pyproject(monkeypatch) -> None:
    """Собранный пакет без исходного pyproject.toml обязан сохранять свою версию."""

    monkeypatch.setattr(project_version.Path, "is_file", lambda _: False)
    assert project_version.get_project_version() == "1.0.0"
