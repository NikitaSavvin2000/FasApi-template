from __future__ import annotations

from pathlib import Path

import pytest

from fastapi_template.configs.config import ConfigurationError, ServerSettings, load_settings


def test_default_server_port_is_8080() -> None:
    """Стандартный запуск должен использовать публично документированный порт 8080."""

    assert ServerSettings().port == 8080


def test_source_precedence_and_nested_partial_overrides(tmp_path: Path) -> None:
    """Приоритет источников обязан сохранять незатронутые вложенные настройки."""

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "server:\n  port: 9100\n  workers: 2\n  thread_pool_tokens: 11\n",
        encoding="utf-8",
    )
    credentials_path = tmp_path / "credential.yaml"
    credentials_path.write_text("credentials:\n  demo_token: from-yaml\n", encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text("APP_SERVER__PORT=9200\n", encoding="utf-8")

    settings = load_settings(
        config_path=config_path,
        credentials_path=credentials_path,
        env_file=env_file,
        environ={
            "APP_LOCAL_DEVELOPMENT": "true",
            "APP_SERVER__PORT": "9300",
            "APP_CREDENTIALS__DEMO_TOKEN": "from-env",
        },
        overrides={"server": {"port": 9400}},
    )

    assert settings.server.port == 9400
    assert settings.server.workers == 2
    assert settings.server.thread_pool_tokens == 11
    assert settings.local_development is True
    assert settings.credentials.demo_token is not None
    assert settings.credentials.demo_token.get_secret_value() == "from-env"


def test_missing_local_flag_defaults_to_false_and_reads_external_url_from_yaml(
    tmp_path: Path,
) -> None:
    """Без APP_LOCAL_DEVELOPMENT выбирается глобальная БД из config.yaml."""

    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="database"):
        load_settings(overrides={"local_development": False}, env_file=env_file, environ={})

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "database:\n  url: postgresql+psycopg://app:password@db.example.test:5432/app\n",
        encoding="utf-8",
    )
    settings = load_settings(config_path=config_path, env_file=env_file, environ={})

    assert settings.local_development is False
    assert settings.database.url == "postgresql+psycopg://app:password@db.example.test:5432/app"


def test_invalid_yaml_unknown_keys_and_missing_explicit_file_are_safe(tmp_path: Path) -> None:
    """Некорректная конфигурация должна завершаться безопасной понятной ошибкой."""

    broken = tmp_path / "broken.yaml"
    broken.write_text("server: [", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="Invalid YAML"):
        load_settings(config_path=broken, environ={})

    unknown = tmp_path / "unknown.yaml"
    unknown.write_text("unexpected: true\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="unexpected"):
        load_settings(config_path=unknown, environ={})

    with pytest.raises(ConfigurationError, match="does not exist"):
        load_settings(config_path=tmp_path / "missing.yaml", environ={})


def test_configuration_rejects_invalid_runtime_combinations(tmp_path: Path) -> None:
    """Reload с несколькими worker-процессами должен отклоняться до запуска."""

    config_path = tmp_path / "config.yaml"
    config_path.write_text("server:\n  reload: true\n  workers: 2\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="server"):
        load_settings(config_path=config_path, environ={})


def test_config_and_credential_files_have_separate_purposes(tmp_path: Path) -> None:
    """Обычная конфигурация и секреты должны оставаться в разных YAML-файлах."""

    config_path = tmp_path / "config.yaml"
    config_path.write_text("credentials:\n  demo_token: should-not-be-here\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="credential.yaml"):
        load_settings(config_path=config_path, environ={})

    credential_path = tmp_path / "credential.yaml"
    credential_path.write_text("server:\n  port: 1\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="Only 'credentials'"):
        load_settings(credentials_path=credential_path, environ={})


@pytest.mark.parametrize(
    "overrides",
    [
        {"cors": {"enabled": True}},
        {"cors": {"allow_origins": ["*"], "allow_credentials": True}},
        {"trusted_hosts": [""]},
    ],
)
def test_unsafe_transport_settings_are_rejected(overrides: dict[str, object]) -> None:
    """Небезопасные CORS и trusted hosts значения должны отклоняться валидацией."""

    with pytest.raises(ConfigurationError):
        load_settings(overrides=overrides, environ={})


def test_invalid_environment_name_and_explicit_env_file_are_rejected(tmp_path: Path) -> None:
    """Неверное имя переменной и отсутствующий явный .env не должны игнорироваться."""

    with pytest.raises(ConfigurationError, match="Invalid environment"):
        load_settings(environ={"APP_SERVER____PORT": "8080"})
    with pytest.raises(ConfigurationError, match="does not exist"):
        load_settings(env_file=tmp_path / "missing.env", environ={})


def test_configuration_path_must_be_a_mapping_file(tmp_path: Path) -> None:
    """Конфигурация должна быть существующим YAML-файлом с объектом верхнего уровня."""

    directory = tmp_path / "directory"
    directory.mkdir()
    with pytest.raises(ConfigurationError, match="not a file"):
        load_settings(config_path=directory, environ={})

    list_config = tmp_path / "list.yaml"
    list_config.write_text("- not\n- a mapping\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="YAML mapping"):
        load_settings(config_path=list_config, environ={})
