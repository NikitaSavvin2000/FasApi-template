from __future__ import annotations

from fastapi_template.services.examples import process_text


def test_process_text_is_deterministic_and_http_independent() -> None:
    """Сервис обязан давать одинаковый результат без зависимости от HTTP-слоя."""

    assert process_text("hello", 2).value == "hello hello"
    assert process_text("hello", 2, uppercase=True).value == "HELLO HELLO"
