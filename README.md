# Шаблон микросервиса FastAPI

FastAPI-сервис с API `/v1` и `/v2`, OpenAPI, локальной SQLite БД и проверками
контракта. Требуются Python 3.11 и [uv](https://docs.astral.sh/uv/).

## Быстрый старт

```bash
uv sync --locked --group dev
source .venv/bin/activate
cp .env.example .env
python main.py
```

Сервис доступен на `http://127.0.0.1:8080`.

```bash
curl http://127.0.0.1:8080/v1/health/ready
open http://127.0.0.1:8080/v1/docs
open http://127.0.0.1:8080/v2/docs
```

## База данных

`APP_LOCAL_DEVELOPMENT=true` в `.env` создаёт
`local_services/local.sqlite3` и применяет `local_services/schema.sql`.

```bash
python local_services/manage.py status
python local_services/manage.py reset
```

Для глобальной БД укажите в `.env` `APP_LOCAL_DEVELOPMENT=false`, создайте
`config.yaml` из примера и заполните `database.url`. Если флаг не задан,
используется `false`.

## Проверки и Git hooks

```bash
python -m pre_commit install --hook-type pre-commit
python -m pre_commit install --hook-type pre-push
python scripts/verify.py all
```

Hook перед commit запускает форматирование, линтер, mypy и тесты. Hook перед
push запускает полный pytest и отменяет обычный push при ошибке.

## Работа с любым AI-агентом

Правила не привязаны к Codex, Claude или конкретной IDE:

- [AGENTS.md](AGENTS.md) — единственные правила разработки для агента;
- [AGENT_TASK.md](AGENT_TASK.md) — пошаговый процесс по задаче со ссылкой;
- [docs/architecture.md](docs/architecture.md) — карта слоёв;
- [.agent/task-template.md](.agent/task-template.md) — шаблон большой задачи.

Передайте агенту задачу с таким текстом:

```text
Прочитай AGENTS.md, AGENT_TASK.md и docs/architecture.md.
Изучи задачу: <ссылка>.
Следуй AGENT_TASK.md: используй существующий код, сначала напиши тест,
а после реализации выполни python scripts/verify.py all.
```

Для частичных проверок доступны `python scripts/verify.py unit`,
`python scripts/verify.py contracts` и `python scripts/verify.py check`.
