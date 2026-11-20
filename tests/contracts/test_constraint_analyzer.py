from __future__ import annotations

from typing import Any

from fastapi_template.utils.openapi_constraints import validate_input_constraints


def _document(schema: dict[str, Any], components: dict[str, Any] | None = None) -> dict[str, Any]:
    """Создаёт минимальную спецификацию для изолированной проверки анализатора."""

    return {
        "paths": {
            "/items": {
                "post": {
                    "requestBody": {
                        "content": {"application/json": {"schema": schema}},
                        "required": True,
                    }
                }
            }
        },
        "components": {"schemas": components or {}},
    }


def test_analyzer_accepts_bounded_schema() -> None:
    """Полностью ограниченная входная схема не должна давать ложных нарушений."""

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "name": {"type": "string", "maxLength": 20},
            "count": {"type": "integer", "minimum": 1, "maximum": 9},
            "tags": {"type": "array", "maxItems": 4, "items": {"type": "string", "maxLength": 8}},
        },
    }
    assert validate_input_constraints(_document(schema)) == []


def test_analyzer_detects_missing_string_and_number_limits() -> None:
    """Анализатор обязан выявлять отсутствующие границы строк и чисел."""

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"name": {"type": "string"}, "count": {"type": "number", "minimum": 0}},
    }
    messages = [violation.message for violation in validate_input_constraints(_document(schema))]
    assert "string lacks maxLength" in messages
    assert "number lacks lower or upper bound" in messages


def test_analyzer_follows_nested_references_and_composes_all_of() -> None:
    """Ссылки и allOf должны образовывать эффективную ограниченную схему."""

    components = {
        "Payload": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"label": {"$ref": "#/components/schemas/Label"}},
        },
        "Label": {"allOf": [{"type": "string", "minLength": 1}, {"maxLength": 12}]},
    }
    assert (
        validate_input_constraints(_document({"$ref": "#/components/schemas/Payload"}, components))
        == []
    )


def test_analyzer_handles_nullable_cycles_and_unbounded_alternatives() -> None:
    """Циклы nullable не зацикливают анализ, а неограниченная ветвь выявляется."""

    components = {
        "Node": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "name": {"type": ["string", "null"], "maxLength": 20},
                "next": {"$ref": "#/components/schemas/Node"},
            },
        }
    }
    assert (
        validate_input_constraints(_document({"$ref": "#/components/schemas/Node"}, components))
        == []
    )

    schema = {
        "oneOf": [
            {"type": "string", "maxLength": 10},
            {"type": "string"},
        ]
    }
    violations = validate_input_constraints(_document(schema))
    assert len(violations) == 1
    assert "oneOf[1]" in violations[0].field_path
