"""Типизированная конфигурация с явным детерминированным приоритетом источников.

Загрузчик объединяет источники до единого прохода валидации Pydantic. Поэтому
частичные вложенные переопределения предсказуемы: программные значения >
окружение процесса > .env > YAML-файлы > значения моделей по умолчанию.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import dotenv_values
from pydantic import (
    BaseModel,
    Field,
    SecretStr,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigurationError(ValueError):
    """Безопасная ошибка конфигурации, не раскрывающая значения секретов."""


class ApplicationSettings(BaseModel):
    name: str = "FastAPI Template"
    environment: Literal["development", "testing", "production"] = "development"


class ServerSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = Field(default=8080, ge=1, le=65535)
    workers: int = Field(default=1, ge=1, le=16)
    reload: bool = False
    thread_pool_tokens: int = Field(default=40, ge=1, le=1_000)

    @model_validator(mode="after")
    def validate_reload_workers(self) -> ServerSettings:
        """Запрещает несовместимое сочетание reload и нескольких процессов."""

        if self.reload and self.workers != 1:
            raise ValueError("server.reload=true requires server.workers=1")
        return self


class LoggingSettings(BaseModel):
    level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"] = "INFO"


class DocumentationSettings(BaseModel):
    enabled: bool = True
    external_base_url: str | None = None


class RequestSettings(BaseModel):
    max_body_bytes: int = Field(default=1_048_576, ge=1_024, le=10_485_760)


class ClientSettings(BaseModel):
    timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    max_connections: int = Field(default=20, ge=1, le=1_000)


class DatabaseSettings(BaseModel):
    """Определяет источник БД для локальной разработки или развернутого окружения."""

    url: str | None = Field(default=None, min_length=10, max_length=4_096)

    @model_validator(mode="after")
    def validate_database_url_format(self) -> DatabaseSettings:
        """Проверяет формат заданного URL без требования его в локальном режиме."""

        if self.url is not None and "://" not in self.url:
            raise ValueError("database.url must be a database connection URL")
        return self


class CorsSettings(BaseModel):
    enabled: bool = False
    allow_origins: list[str] = Field(default_factory=list)
    allow_credentials: bool = False

    @model_validator(mode="after")
    def validate_origins(self) -> CorsSettings:
        """Проверяет, что включённый CORS не ослабляет политику небезопасно."""

        if self.enabled and not self.allow_origins:
            raise ValueError("cors.allow_origins must be set when cors.enabled=true")
        if self.allow_credentials and "*" in self.allow_origins:
            raise ValueError("cors.allow_credentials cannot be used with a wildcard origin")
        return self


class CredentialsSettings(BaseModel):
    """Резерв для реальных интеграций; шаблону учётные данные не требуются."""

    demo_token: SecretStr | None = None


class Settings(BaseSettings):
    """Все настройки времени выполнения после иерархического объединения источников."""

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_nested_delimiter="__",
        extra="forbid",
        validate_default=True,
    )

    app: ApplicationSettings = Field(default_factory=ApplicationSettings)
    local_development: bool = False
    server: ServerSettings = Field(default_factory=ServerSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    docs: DocumentationSettings = Field(default_factory=DocumentationSettings)
    request: RequestSettings = Field(default_factory=RequestSettings)
    client: ClientSettings = Field(default_factory=ClientSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    cors: CorsSettings = Field(default_factory=CorsSettings)
    trusted_hosts: list[str] = Field(default_factory=list)
    credentials: CredentialsSettings = Field(default_factory=CredentialsSettings)

    @field_validator("database")
    @classmethod
    def validate_database_source(
        cls, database: DatabaseSettings, info: ValidationInfo
    ) -> DatabaseSettings:
        """Требует глобальный URL БД, когда локальная разработка выключена."""

        if not info.data.get("local_development", False) and database.url is None:
            raise ValueError("database.url must be set when local_development=false")
        return database

    @field_validator("trusted_hosts")
    @classmethod
    def validate_hosts(cls, hosts: list[str]) -> list[str]:
        """Не допускает пустые значения в списке доверенных хостов."""

        if any(not host.strip() for host in hosts):
            raise ValueError("trusted_hosts cannot contain empty values")
        return hosts


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Рекурсивно объединяет словари, сохраняя незатронутые вложенные значения."""

    result = base.copy()
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = _deep_merge(dict(result[key]), value)
        else:
            result[key] = value
    return result


def _load_yaml(
    path: Path, *, required: bool, expected_top_level: str | None = None
) -> dict[str, Any]:
    """Безопасно читает YAML-словарь и проверяет назначение его верхнего уровня."""

    if not path.exists():
        if required:
            raise ConfigurationError(f"Configuration file does not exist: {path}")
        return {}
    if not path.is_file():
        raise ConfigurationError(f"Configuration path is not a file: {path}")
    try:
        with path.open(encoding="utf-8") as file:
            content = yaml.safe_load(file) or {}
    except yaml.YAMLError as error:
        raise ConfigurationError(f"Invalid YAML in {path}") from error
    if not isinstance(content, dict):
        raise ConfigurationError(f"Configuration file must contain a YAML mapping: {path}")
    if expected_top_level is not None and set(content) - {expected_top_level}:
        raise ConfigurationError(f"Only '{expected_top_level}' is allowed in {path}")
    return content


def _environment_to_nested(values: Mapping[str, str | None]) -> dict[str, Any]:
    """Преобразует переменные `APP_` с разделителем `__` во вложенный словарь."""

    nested: dict[str, Any] = {}
    for name, value in values.items():
        if value is None or not name.startswith("APP_"):
            continue
        parts = name.removeprefix("APP_").lower().split("__")
        if not all(parts):
            raise ConfigurationError(f"Invalid environment variable name: {name}")
        target = nested
        for part in parts[:-1]:
            existing = target.setdefault(part, {})
            if not isinstance(existing, dict):
                raise ConfigurationError(f"Conflicting environment variable name: {name}")
            target = existing
        target[parts[-1]] = value
    return nested


def _validation_error(error: ValidationError) -> ConfigurationError:
    """Преобразует ошибку Pydantic в сообщение без значений конфигурации."""

    locations = [".".join(str(part) for part in issue["loc"]) for issue in error.errors()]
    return ConfigurationError(f"Invalid configuration fields: {', '.join(locations)}")


def _resolve_path(path: str | Path | None, default_name: str) -> tuple[Path, bool]:
    """Разрешает явный или неявный путь относительно рабочего каталога."""

    if path is None:
        return Path.cwd() / default_name, False
    candidate = Path(path).expanduser()
    return (candidate if candidate.is_absolute() else Path.cwd() / candidate), True


def load_settings(
    *,
    config_path: str | Path | None = None,
    credentials_path: str | Path | None = None,
    env_file: str | Path | None = None,
    overrides: Mapping[str, Any] | None = None,
    environ: Mapping[str, str | None] | None = None,
) -> Settings:
    """Загружает настройки, не читая файлы разработчика вне рабочего каталога.

    Явные относительные пути разрешаются от рабочего каталога процесса.
    Отсутствие неявных ``config.yaml``, ``credential.yaml`` или ``.env``
    допустимо; отсутствие явно указанного пути — ошибка.
    """

    resolved_config, config_is_explicit = _resolve_path(config_path, "config.yaml")
    resolved_credentials, credentials_are_explicit = _resolve_path(
        credentials_path, "credential.yaml"
    )
    resolved_env, env_is_explicit = _resolve_path(env_file, ".env")

    ordinary_yaml = _load_yaml(resolved_config, required=config_is_explicit)
    credentials_yaml = _load_yaml(
        resolved_credentials,
        required=credentials_are_explicit,
        expected_top_level="credentials",
    )
    if "credentials" in ordinary_yaml:
        raise ConfigurationError("Put secret settings in credential.yaml, not config.yaml")

    dotenv_source: Mapping[str, str | None]
    if resolved_env.exists():
        dotenv_source = dotenv_values(resolved_env)
    elif env_is_explicit:
        raise ConfigurationError(f"Configuration file does not exist: {resolved_env}")
    else:
        dotenv_source = {}

    process_environment = os.environ if environ is None else environ
    merged = _deep_merge(ordinary_yaml, credentials_yaml)
    merged = _deep_merge(merged, _environment_to_nested(dotenv_source))
    merged = _deep_merge(merged, _environment_to_nested(process_environment))
    if overrides is not None:
        merged = _deep_merge(merged, overrides)
    try:
        return Settings.model_validate(merged)
    except ValidationError as error:
        raise _validation_error(error) from error
