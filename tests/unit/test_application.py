from __future__ import annotations

from starlette.testclient import TestClient

from fastapi_template.configs.config import Settings
from fastapi_template.core.version import API_PREFIX
from fastapi_template.db.database import list_local_tables
from fastapi_template.main import create_app


def test_lifespan_sets_thread_limiter_and_releases_resources() -> None:
    """Lifespan обязан помечать приложение готовым и освобождать ресурсы при выходе."""

    app = create_app(
        Settings.model_validate({"local_development": True, "server": {"thread_pool_tokens": 3}})
    )
    with TestClient(app):
        assert app.state.ready is True
        assert app.state.resources_closed is False
        assert app.state.database_target.source == "local"
        assert {"schema_versions", "example_records"} <= list_local_tables(
            app.state.database_target
        )
        for version_app in app.state.version_apps.values():
            assert version_app.state.ready is True
            assert version_app.state.resources_closed is False
            assert version_app.state.database_target == app.state.database_target
    assert app.state.ready is False
    assert app.state.resources_closed is True
    for version_app in app.state.version_apps.values():
        assert version_app.state.ready is False
        assert version_app.state.resources_closed is True


def test_documentation_can_be_disabled() -> None:
    """Отключение документации не должно регистрировать её URL в приложении."""

    app = create_app(
        Settings.model_validate({"local_development": True, "docs": {"enabled": False}})
    )
    for version_app in app.state.version_apps.values():
        assert version_app.docs_url is None
        assert version_app.redoc_url is None
        assert version_app.openapi_url is None


def test_validation_error_does_not_return_rejected_request_value() -> None:
    """Ответ 422 не должен раскрывать текст, который клиент передал невалидным."""

    rejected_text = "конфиденциальное-некорректное-значение"
    with TestClient(create_app(Settings.model_validate({"local_development": True}))) as client:
        response = client.post(
            f"{API_PREFIX}/examples/process",
            json={"text": rejected_text, "repetitions": 0},
        )

    assert response.status_code == 422
    assert rejected_text not in response.text
    assert all(set(detail) == {"type", "loc", "msg"} for detail in response.json()["detail"])


def test_transport_middleware_enforces_configured_host_and_cors_policy() -> None:
    """Доверенный хост и разрешённый Origin должны применяться к versioned API."""

    settings = Settings.model_validate(
        {
            "local_development": True,
            "trusted_hosts": ["api.example.test"],
            "cors": {"enabled": True, "allow_origins": ["https://web.example.test"]},
        }
    )
    with TestClient(create_app(settings)) as client:
        rejected = client.get(f"{API_PREFIX}/openapi.json", headers={"host": "blocked.test"})
        accepted = client.get(
            f"{API_PREFIX}/openapi.json",
            headers={"host": "api.example.test", "origin": "https://web.example.test"},
        )

    assert rejected.status_code == 400
    assert accepted.status_code == 200
    assert accepted.headers["access-control-allow-origin"] == "https://web.example.test"


def test_lifespan_exposes_external_database_target_without_local_initialization() -> None:
    """Внешний режим должен передать URL в приложение, не подменяя его SQLite-файлом."""

    database_url = "postgresql+psycopg://app:password@db.example.test:5432/app"
    settings = Settings.model_validate(
        {"local_development": False, "database": {"url": database_url}}
    )
    app = create_app(settings)

    with TestClient(app):
        assert app.state.database_target.source == "external"
        assert app.state.database_target.url == database_url
        assert app.state.database_target.local_path is None
