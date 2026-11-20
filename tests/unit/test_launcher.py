from __future__ import annotations

from unittest.mock import Mock

from fastapi_template.__main__ import run_server
from fastapi_template.configs.config import Settings


def test_launcher_passes_workers_and_importable_factory(monkeypatch) -> None:
    """Лаунчер обязан передавать число процессов и импортируемую фабрику Uvicorn."""

    run = Mock()
    monkeypatch.setattr("fastapi_template.__main__.uvicorn.run", run)
    settings = Settings.model_validate(
        {
            "local_development": True,
            "server": {"host": "0.0.0.0", "port": 8765, "workers": 2, "thread_pool_tokens": 4},
        }
    )

    run_server(settings)

    assert run.call_args.args == ("fastapi_template.main:create_app",)
    assert run.call_args.kwargs["factory"] is True
    assert run.call_args.kwargs["workers"] == 2
    assert run.call_args.kwargs["port"] == 8765
