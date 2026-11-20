"""Единые воспроизводимые проверки шаблона для разработчика и AI-агента."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _python_module(*arguments: str) -> list[str]:
    """Возвращает команду запуска Python-модуля из активного окружения."""

    return [sys.executable, "-m", *arguments]


def _commands(mode: str) -> tuple[list[str], ...]:
    """Собирает минимальный набор проверок для выбранного режима."""

    checks = (
        _python_module("ruff", "format", "--check", "."),
        _python_module("ruff", "check", "."),
        _python_module("mypy", "src"),
    )
    if mode == "unit":
        return (_python_module("pytest", "--no-cov", "-v", "tests/unit"),)
    if mode == "contracts":
        return (_python_module("pytest", "--no-cov", "-v", "tests/contracts"),)
    if mode == "check":
        return checks
    if mode == "all":
        return (
            ("uv", "lock", "--check"),
            *checks,
            _python_module("pytest", "-v"),
            ("uv", "build"),
        )
    raise ValueError(f"Неизвестный режим проверки: {mode}")


def _run(command: Sequence[str]) -> None:
    """Запускает одну проверку в корне репозитория и останавливается при ошибке."""

    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def _parse_args() -> argparse.Namespace:
    """Принимает режим проверки без неявных действий с репозиторием."""

    parser = argparse.ArgumentParser(description="Проверки шаблона FastAPI")
    parser.add_argument("mode", choices=("unit", "contracts", "check", "all"))
    return parser.parse_args()


def main() -> None:
    """Выполняет выбранный воспроизводимый набор проверок."""

    for command in _commands(_parse_args().mode):
        _run(command)


if __name__ == "__main__":
    main()
