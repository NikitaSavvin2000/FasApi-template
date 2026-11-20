"""Политика проверки ограничений входных схем OpenAPI.

Модуль намеренно отделён от моделей FastAPI/Pydantic: контрактные тесты получают
спецификацию работающего сервера и анализируют её эффективные схемы здесь.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

Schema = Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ConstraintViolation:
    method: str
    route: str
    field_path: str
    message: str

    def render(self) -> str:
        """Формирует понятное сообщение о нарушении политики ограничений."""

        return f"{self.method.upper()} {self.route} {self.field_path}: {self.message}"


class _Resolver:
    def __init__(self, document: Mapping[str, Any]) -> None:
        """Сохраняет OpenAPI-документ для разрешения локальных ссылок."""

        self.document = document

    def resolve(self, reference: str) -> Schema:
        """Возвращает схему по локальной JSON Pointer-ссылке OpenAPI."""

        if not reference.startswith("#/"):
            raise ValueError(f"Only local OpenAPI references are supported: {reference}")
        target: Any = self.document
        for part in reference[2:].split("/"):
            if not isinstance(target, Mapping):
                raise ValueError(f"Reference does not resolve to a schema: {reference}")
            target = target[part.replace("~1", "/").replace("~0", "~")]
        if not isinstance(target, Mapping):
            raise ValueError(f"Reference does not resolve to a schema: {reference}")
        return target


def _bound(schema: Schema, minimum: str, maximum: str) -> bool:
    """Проверяет наличие обеих границ для числовой политики."""

    return minimum in schema and maximum in schema


def _merge_all_of(
    parts: Iterable[Schema], resolver: _Resolver, seen_refs: set[str]
) -> dict[str, Any]:
    """Консервативно объединяет ограничения, важные для политики входных данных."""

    merged: dict[str, Any] = {}
    for raw_part in parts:
        part = _dereference(raw_part, resolver, seen_refs.copy())
        nested = part.get("allOf")
        if isinstance(nested, list):
            part = _merge_all_of(
                [candidate for candidate in nested if isinstance(candidate, Mapping)],
                resolver,
                seen_refs,
            )
        for key, value in part.items():
            if key == "allOf":
                continue
            if key in {"maximum", "maxLength", "maxItems", "maxProperties"}:
                merged[key] = min(merged[key], value) if key in merged else value
            elif key in {"minimum", "minLength", "minItems", "minProperties"}:
                merged[key] = max(merged[key], value) if key in merged else value
            elif key == "required":
                previous = merged.setdefault(key, [])
                merged[key] = list(dict.fromkeys([*previous, *value]))
            elif key == "properties" and isinstance(value, Mapping):
                previous_properties = merged.setdefault(key, {})
                for property_name, property_schema in value.items():
                    if property_name in previous_properties:
                        previous_properties[property_name] = {
                            "allOf": [previous_properties[property_name], property_schema]
                        }
                    else:
                        previous_properties[property_name] = property_schema
            elif key == "additionalProperties" and key in merged:
                if value is False or merged[key] is False:
                    merged[key] = False
                else:
                    merged[key] = value
            else:
                merged[key] = value
    return merged


def _dereference(schema: Schema, resolver: _Resolver, seen_refs: set[str]) -> Schema:
    """Разрешает $ref и объединяет соседние ограничения без бесконечной рекурсии."""

    reference = schema.get("$ref")
    if not isinstance(reference, str):
        return schema
    if reference in seen_refs:
        # A recursive schema is already being checked at its first occurrence.
        return {}
    seen_refs.add(reference)
    target = _dereference(resolver.resolve(reference), resolver, seen_refs)
    siblings = {key: value for key, value in schema.items() if key != "$ref"}
    return _merge_all_of([target, siblings], resolver, seen_refs) if siblings else target


def _types(schema: Schema) -> set[str]:
    """Определяет фактические JSON-типы схемы с nullable-представлением."""

    declared = schema.get("type")
    if isinstance(declared, str):
        return {declared}
    if isinstance(declared, list):
        return {item for item in declared if isinstance(item, str) and item != "null"}
    if "properties" in schema or "additionalProperties" in schema:
        return {"object"}
    if "items" in schema:
        return {"array"}
    return set()


def _inspect_schema(
    schema: Schema,
    *,
    method: str,
    route: str,
    field_path: str,
    resolver: _Resolver,
    seen_refs: set[str],
) -> list[ConstraintViolation]:
    """Рекурсивно проверяет эффективные ограничения одной входной схемы."""

    reference = schema.get("$ref")
    if isinstance(reference, str):
        if reference in seen_refs:
            return []
        return _inspect_schema(
            resolver.resolve(reference),
            method=method,
            route=route,
            field_path=field_path,
            resolver=resolver,
            seen_refs={*seen_refs, reference},
        )
    if isinstance(schema.get("allOf"), list):
        effective = _merge_all_of(
            [part for part in schema["allOf"] if isinstance(part, Mapping)], resolver, seen_refs
        )
        return _inspect_schema(
            effective,
            method=method,
            route=route,
            field_path=field_path,
            resolver=resolver,
            seen_refs=seen_refs,
        )

    violations: list[ConstraintViolation] = []
    for keyword in ("anyOf", "oneOf"):
        alternatives = schema.get(keyword)
        if isinstance(alternatives, list):
            for index, branch in enumerate(alternatives):
                if isinstance(branch, Mapping):
                    violations.extend(
                        _inspect_schema(
                            branch,
                            method=method,
                            route=route,
                            field_path=f"{field_path}.{keyword}[{index}]",
                            resolver=resolver,
                            seen_refs=seen_refs.copy(),
                        )
                    )
            return violations

    if "const" in schema or (isinstance(schema.get("enum"), list) and schema["enum"]):
        return violations

    types = _types(schema)
    if "string" in types and "maxLength" not in schema:
        violations.append(ConstraintViolation(method, route, field_path, "string lacks maxLength"))
    if {"number", "integer"} & types and not _bound(schema, "minimum", "maximum"):
        violations.append(
            ConstraintViolation(method, route, field_path, "number lacks lower or upper bound")
        )
    if "array" in types:
        if "maxItems" not in schema:
            violations.append(
                ConstraintViolation(method, route, field_path, "array lacks maxItems")
            )
        items = schema.get("items")
        if isinstance(items, Mapping):
            violations.extend(
                _inspect_schema(
                    items,
                    method=method,
                    route=route,
                    field_path=f"{field_path}[]",
                    resolver=resolver,
                    seen_refs=seen_refs.copy(),
                )
            )
    if "object" in types:
        additional = schema.get("additionalProperties")
        if additional is not False and not isinstance(additional, Mapping):
            violations.append(
                ConstraintViolation(
                    method,
                    route,
                    field_path,
                    "object must set additionalProperties to false or define bounded values",
                )
            )
        if isinstance(additional, Mapping):
            if "maxProperties" not in schema:
                violations.append(
                    ConstraintViolation(method, route, field_path, "dictionary lacks maxProperties")
                )
            violations.extend(
                _inspect_schema(
                    additional,
                    method=method,
                    route=route,
                    field_path=f"{field_path}.*",
                    resolver=resolver,
                    seen_refs=seen_refs.copy(),
                )
            )
        properties = schema.get("properties")
        if isinstance(properties, Mapping):
            for name, child in properties.items():
                if isinstance(child, Mapping):
                    violations.extend(
                        _inspect_schema(
                            child,
                            method=method,
                            route=route,
                            field_path=f"{field_path}.{name}",
                            resolver=resolver,
                            seen_refs=seen_refs.copy(),
                        )
                    )
    return violations


def validate_input_constraints(document: Mapping[str, Any]) -> list[ConstraintViolation]:
    """Возвращает нарушения политики для тел запросов и всех параметров OpenAPI."""

    resolver = _Resolver(document)
    violations: list[ConstraintViolation] = []
    paths = document.get("paths", {})
    if not isinstance(paths, Mapping):
        return [ConstraintViolation("document", "/", "$", "paths must be an object")]
    for route, path_item in paths.items():
        if not isinstance(route, str) or not isinstance(path_item, Mapping):
            continue
        inherited_parameters = path_item.get("parameters", [])
        for method, operation in path_item.items():
            if method.lower() not in {"get", "put", "post", "delete", "patch", "head", "options"}:
                continue
            if not isinstance(operation, Mapping):
                continue
            parameters = [*inherited_parameters, *operation.get("parameters", [])]
            for parameter in parameters:
                if not isinstance(parameter, Mapping):
                    continue
                parameter_schema = parameter.get("schema")
                if isinstance(parameter_schema, Mapping):
                    name = parameter.get("name", "unnamed")
                    location = parameter.get("in", "unknown")
                    violations.extend(
                        _inspect_schema(
                            parameter_schema,
                            method=method,
                            route=route,
                            field_path=f"{location}.{name}",
                            resolver=resolver,
                            seen_refs=set(),
                        )
                    )
            request_body = operation.get("requestBody")
            if not isinstance(request_body, Mapping):
                continue
            content = request_body.get("content", {})
            if not isinstance(content, Mapping):
                continue
            for media_type, media in content.items():
                if isinstance(media, Mapping) and isinstance(media.get("schema"), Mapping):
                    violations.extend(
                        _inspect_schema(
                            media["schema"],
                            method=method,
                            route=route,
                            field_path=f"body[{media_type}]",
                            resolver=resolver,
                            seen_refs=set(),
                        )
                    )
    return violations
