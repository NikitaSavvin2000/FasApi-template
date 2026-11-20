# Карта архитектуры

## Поток запроса

```text
main.py → fastapi_template.__main__ → create_app()
        → root middleware → /vN mounted FastAPI application
        → api/vN/routes → api/dependencies → services → db
```

Корневое приложение отвечает за middleware и lifecycle. Каждая версия API
монтируется как отдельное FastAPI-приложение, поэтому её Swagger и OpenAPI не
содержат маршруты другой версии.

## Слои

| Слой | Ответственность | Не должен зависеть от |
| --- | --- | --- |
| `api/` | HTTP, parsing, DI, OpenAPI | деталей хранения данных |
| `schemas/` | публичные DTO и валидация | FastAPI route-логики |
| `services/` | прикладные правила | FastAPI и SQL-клиентов |
| `models/` | доменные значения | HTTP и БД |
| `db/` | источник БД и репозитории | route handler-ов |
| `core/` | инфраструктура приложения | прикладных сценариев |

## Настройки и данные

`Settings` строится в `configs/config.py`. Локальный режим определяется только
`APP_LOCAL_DEVELOPMENT`:

```text
true  → local_services/local.sqlite3 + local_services/schema.sql
false → database.url из config.yaml или окружения
```

Локальный SQLite-файл не коммитится. SQL-шаблон и утилита управления остаются
в `local_services/`.

## Тестовые границы

- `tests/unit/`: функции, конфигурация, lifecycle и инфраструктура.
- `tests/contracts/`: живой процесс, OpenAPI и документированные операции без
  перечня route-путей.
- Новая функциональность получает минимальный тест на наблюдаемое поведение до
  реализации.
