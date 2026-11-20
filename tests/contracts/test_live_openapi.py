"""Универсальные проверки контракта OpenAPI работающего сервиса."""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx2 as httpx
import pytest
from jsonschema import Draft202012Validator
from openapi_spec_validator import validate
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
from starlette.testclient import TestClient

from fastapi_template.core.version import API_PREFIX, API_PREFIXES, PROJECT_VERSION
from fastapi_template.utils.openapi_constraints import validate_input_constraints

ROOT = Path(__file__).resolve().parents[2]
HTTP_METHODS = {"get", "put", "post", "delete", "patch", "head", "options"}


def _operations(document: Mapping[str, Any]) -> Iterator[tuple[str, str, Mapping[str, Any]]]:
    """Перебирает все документированные HTTP-операции без знания их имён."""

    paths = document.get("paths", {})
    assert isinstance(paths, Mapping), "OpenAPI paths должен быть объектом"
    for path, item in paths.items():
        assert isinstance(path, str) and isinstance(item, Mapping)
        for method, operation in item.items():
            if method.lower() in HTTP_METHODS:
                assert isinstance(operation, Mapping)
                yield method.lower(), path, operation


def _versioned_operations(
    documents: Mapping[str, Mapping[str, Any]],
) -> Iterator[tuple[str, str, str, Mapping[str, Any]]]:
    """Перебирает операции с URL-префиксом приложения, которому они принадлежат."""

    for prefix, document in documents.items():
        for method, path, operation in _operations(document):
            yield prefix, method, path, operation


def _resolve(document: Mapping[str, Any], schema: Mapping[str, Any]) -> Mapping[str, Any]:
    """Разрешает локальную ссылку схемы OpenAPI до фактического объекта."""

    resolved: Mapping[str, Any] = schema
    seen: set[str] = set()
    while isinstance(resolved.get("$ref"), str):
        reference = resolved["$ref"]
        assert isinstance(reference, str) and reference.startswith("#/")
        assert reference not in seen, f"Циклическая ссылка схемы: {reference}"
        seen.add(reference)
        target: Any = document
        for part in reference.removeprefix("#/").split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        assert isinstance(target, Mapping)
        resolved = target
    return resolved


def _validator(document: Mapping[str, Any], schema: Mapping[str, Any]) -> Draft202012Validator:
    """Создаёт валидатор JSON Schema с доступом к локальным компонентам OpenAPI."""

    registry = Registry().with_resource(
        "urn:fastapi-template:openapi",
        Resource.from_contents(dict(document), default_specification=DRAFT202012),
    )
    validator_schema = dict(schema)
    reference = validator_schema.get("$ref")
    if isinstance(reference, str) and reference.startswith("#/"):
        validator_schema["$ref"] = f"urn:fastapi-template:openapi{reference}"
    return Draft202012Validator(validator_schema, registry=registry)


def _examples(media: Mapping[str, Any]) -> Iterable[Any]:
    """Возвращает все примеры OpenAPI из объекта media type."""

    if "example" in media:
        yield media["example"]
    examples = media.get("examples", {})
    if isinstance(examples, Mapping):
        for named_example in examples.values():
            if isinstance(named_example, Mapping) and "value" in named_example:
                yield named_example["value"]


def _sample_value(schema: Mapping[str, Any]) -> Any:
    """Берёт документированное значение параметра для универсального HTTP-вызова."""

    if "example" in schema:
        return schema["example"]
    examples = schema.get("examples")
    if isinstance(examples, list) and examples:
        return examples[0]
    if "default" in schema:
        return schema["default"]
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]
    raise AssertionError("Для обязательного параметра нужен example, examples, default или enum")


def _request_arguments(
    document: Mapping[str, Any], path: str, operation: Mapping[str, Any]
) -> tuple[str, dict[str, Any]]:
    """Строит HTTP-аргументы из примеров и значений по умолчанию спецификации."""

    url_path = path
    kwargs: dict[str, Any] = {"params": {}, "headers": {}, "cookies": {}}
    parameters = operation.get("parameters", [])
    assert isinstance(parameters, list)
    for parameter in parameters:
        assert isinstance(parameter, Mapping)
        schema = parameter.get("schema", {})
        assert isinstance(schema, Mapping)
        if not parameter.get("required", False) and "default" not in schema:
            continue
        value = _sample_value(_resolve(document, schema))
        name = parameter.get("name")
        location = parameter.get("in")
        assert isinstance(name, str) and isinstance(location, str)
        if location == "path":
            url_path = url_path.replace(f"{{{name}}}", quote(str(value), safe=""))
        elif location == "query":
            kwargs["params"][name] = value
        elif location == "header":
            kwargs["headers"][name] = str(value)
        elif location == "cookie":
            kwargs["cookies"][name] = str(value)
        else:
            raise AssertionError(f"Неподдерживаемое расположение параметра: {location}")

    request_body = operation.get("requestBody")
    if not isinstance(request_body, Mapping):
        for key in ("params", "headers", "cookies"):
            if not kwargs[key]:
                del kwargs[key]
        return url_path, kwargs
    content = request_body.get("content", {})
    assert isinstance(content, Mapping) and content, "Тело запроса должно описывать content"
    media_type, media = next(iter(content.items()))
    assert isinstance(media_type, str) and isinstance(media, Mapping)
    examples = list(_examples(media))
    if request_body.get("required", False):
        assert examples, "Для обязательного тела запроса нужен пример"
    if examples:
        if media_type == "application/json":
            kwargs["json"] = examples[0]
        else:
            kwargs["content"] = examples[0]
            kwargs["headers"]["content-type"] = media_type
    for key in ("params", "headers", "cookies"):
        if not kwargs[key]:
            del kwargs[key]
    return url_path, kwargs


def _assert_documented_schema(document: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    """Проверяет описания и примеры свойств публичной Pydantic-схемы."""

    resolved = _resolve(document, schema)
    properties = resolved.get("properties")
    if isinstance(properties, Mapping):
        assert resolved.get("description"), "У публичной объектной схемы требуется description"
        for name, property_schema in properties.items():
            assert isinstance(name, str) and isinstance(property_schema, Mapping)
            effective = _resolve(document, property_schema)
            assert effective.get("description"), f"У поля {name} требуется description"
            has_example = any(
                key in effective for key in ("example", "examples", "default", "enum", "const")
            )
            assert has_example, f"У поля {name} требуется пример или конечное значение"
            _assert_documented_schema(document, effective)
    items = resolved.get("items")
    if isinstance(items, Mapping):
        _assert_documented_schema(document, items)
    for composition in ("allOf", "anyOf", "oneOf"):
        branches = resolved.get(composition)
        if isinstance(branches, list):
            for branch in branches:
                if isinstance(branch, Mapping):
                    _assert_documented_schema(document, branch)


@pytest.fixture(scope="session")
def live_openapi(running_server: str) -> dict[str, dict[str, Any]]:
    """Извлекает независимые контракты OpenAPI всех опубликованных версий API."""

    documents: dict[str, dict[str, Any]] = {}
    for prefix in API_PREFIXES:
        response = httpx.get(f"{running_server}{prefix}/openapi.json", timeout=5)
        assert response.status_code == 200
        document = response.json()
        assert isinstance(document, dict)
        documents[prefix] = document
    return documents


@pytest.fixture
def in_process_openapi(client: TestClient) -> dict[str, dict[str, Any]]:
    """Получает контракты всех версий у экземпляра, работающего в тестовом процессе."""

    documents: dict[str, dict[str, Any]] = {}
    for prefix in API_PREFIXES:
        response = client.get(f"{prefix}/openapi.json")
        assert response.status_code == 200
        document = response.json()
        assert isinstance(document, dict)
        documents[prefix] = document
    return documents


def test_live_openapi_is_valid_versioned_and_isolated(
    live_openapi: dict[str, dict[str, Any]],
) -> None:
    """Проверяет валидность и независимость контрактов опубликованных версий API."""

    with (ROOT / "pyproject.toml").open("rb") as file:
        pyproject = tomllib.load(file)
    assert len(live_openapi) >= 2, "Нужно публиковать документацию нескольких версий API"
    assert f"/v{PROJECT_VERSION.split('.', maxsplit=1)[0]}" == API_PREFIX
    operation_ids_by_version: dict[str, set[str]] = {}
    for prefix, document in live_openapi.items():
        validate(document)
        assert document["info"]["version"] == pyproject["project"]["version"] == PROJECT_VERSION
        operations = list(_operations(document))
        assert operations, f"{prefix}: OpenAPI должен содержать хотя бы одну HTTP-операцию"
        operation_ids = [operation.get("operationId") for _, _, operation in operations]
        assert all(isinstance(operation_id, str) and operation_id for operation_id in operation_ids)
        assert len(operation_ids) == len(set(operation_ids))
        operation_ids_by_version[prefix] = set(operation_ids)
    for prefix, operation_ids in operation_ids_by_version.items():
        for other_prefix, other_operation_ids in operation_ids_by_version.items():
            if prefix != other_prefix:
                assert operation_ids.isdisjoint(other_operation_ids), (
                    f"{prefix}: контракт содержит операции из документации {other_prefix}"
                )


def test_each_version_documentation_loads_its_own_openapi_contract(client: TestClient) -> None:
    """Swagger каждой версии должен запрашивать только её отдельную OpenAPI-спецификацию."""

    for prefix in API_PREFIXES:
        response = client.get(f"{prefix}/docs")
        assert response.status_code == 200
        assert f"{prefix}/openapi.json" in response.text


def test_every_live_operation_has_descriptions_examples_and_bounded_input(
    live_openapi: dict[str, dict[str, Any]],
) -> None:
    """Проверяет документацию и ограничения всех добавленных маршрутов без списка путей."""

    for prefix, document in live_openapi.items():
        violations = validate_input_constraints(document)
        assert not violations, "\n".join(violation.render() for violation in violations)
        for _, path, operation in _operations(document):
            assert operation.get("summary"), f"{prefix}{path}: требуется summary"
            assert operation.get("description"), f"{prefix}{path}: требуется description"
            for parameter in operation.get("parameters", []):
                assert isinstance(parameter, Mapping)
                assert parameter.get("description"), (
                    f"У параметра {parameter.get('name')} нужен description"
                )
                schema = parameter.get("schema")
                assert isinstance(schema, Mapping)
                if parameter.get("required", False):
                    _sample_value(_resolve(document, schema))
            request_body = operation.get("requestBody")
            if isinstance(request_body, Mapping):
                for media in request_body.get("content", {}).values():
                    assert isinstance(media, Mapping)
                    schema = media.get("schema")
                    assert isinstance(schema, Mapping)
                    _assert_documented_schema(document, schema)
                    if request_body.get("required", False):
                        assert list(_examples(media)), f"У тела запроса {path} нужен пример"
            responses = operation.get("responses", {})
            assert isinstance(responses, Mapping) and responses
            for status, response in responses.items():
                assert isinstance(response, Mapping) and response.get("description"), (
                    f"У ответа {status} операции {path} требуется description"
                )
                if not str(status).startswith("2"):
                    continue
                for media in response.get("content", {}).values():
                    assert isinstance(media, Mapping)
                    assert list(_examples(media)), f"У успешного ответа {path} нужен пример"
                    schema = media.get("schema")
                    assert isinstance(schema, Mapping), f"У успешного ответа {path} нужна схема"
                    effective_schema = _resolve(document, schema)
                    assert effective_schema.get("description"), (
                        f"У схемы успешного ответа {path} требуется description"
                    )
                    _assert_documented_schema(document, schema)


def test_documented_examples_call_every_operation(
    client: TestClient, in_process_openapi: dict[str, dict[str, Any]]
) -> None:
    """Вызывает все маршруты из их OpenAPI-примеров и валидирует ответы."""

    for prefix, method, path, operation in _versioned_operations(in_process_openapi):
        document = in_process_openapi[prefix]
        url_path, kwargs = _request_arguments(document, path, operation)
        response = client.request(method, f"{prefix}{url_path}", **kwargs)
        responses = operation["responses"]
        assert str(response.status_code) in responses, (
            f"{method.upper()} {path}: неожиданный статус"
        )
        if not response.content:
            continue
        content_type = response.headers["content-type"].split(";", maxsplit=1)[0]
        media = responses[str(response.status_code)].get("content", {}).get(content_type)
        assert isinstance(media, Mapping), f"{method.upper()} {path}: media type не описан"
        schema = media.get("schema")
        if isinstance(schema, Mapping) and content_type == "application/json":
            _validator(document, schema).validate(response.json())
