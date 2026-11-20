from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx2 as httpx
import pytest
from starlette.testclient import TestClient

from fastapi_template.configs.config import Settings
from fastapi_template.core.version import API_PREFIXES
from fastapi_template.main import create_app

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings() -> Settings:
    """Создаёт изолированные настройки приложения для внутрипроцессных тестов."""

    return Settings.model_validate({"local_development": True, "server": {"thread_pool_tokens": 4}})


@pytest.fixture
def app(settings: Settings):
    """Создаёт новый экземпляр приложения с тестовыми настройками."""

    return create_app(settings)


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    """Предоставляет HTTP-клиент с запущенным lifespan приложения."""

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def running_server() -> Iterator[str]:
    """Запускает сервис отдельным процессом для контрактных и потоковых тестов."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    environment = {key: value for key, value in os.environ.items() if not key.startswith("APP_")}
    environment.update(
        {
            "APP_SERVER__HOST": "127.0.0.1",
            "APP_SERVER__PORT": str(port),
            "APP_SERVER__THREAD_POOL_TOKENS": "3",
            "APP_LOGGING__LEVEL": "WARNING",
            "APP_LOCAL_DEVELOPMENT": "true",
        }
    )
    process = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                if all(
                    httpx.get(f"{base_url}{prefix}/openapi.json", timeout=0.25).status_code == 200
                    for prefix in API_PREFIXES
                ):
                    break
            except httpx.HTTPError:
                time.sleep(0.1)
        else:
            output = process.communicate(timeout=1)[0]
            pytest.fail(f"Сервер не стал готов за отведённое время:\n{output}")
        yield base_url
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
            process.wait(timeout=5)
        if process.stdout is not None:
            process.stdout.close()
