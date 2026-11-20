"""Детерминированные сценарии, общие для версий API."""

from __future__ import annotations

from fastapi_template.models.examples import ProcessedText


def process_text(text: str, repetitions: int, *, uppercase: bool = False) -> ProcessedText:
    """Повторяет валидированный текст; вторая версия меняет его представление."""

    source = text.upper() if uppercase else text
    return ProcessedText(value=" ".join([source] * repetitions), repetitions=repetitions)
