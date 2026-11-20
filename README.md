# Шаблон микросервиса FastAPI

FastAPI-сервис с API `/v1` и `/v2`, локальной SQLite БД для разработки и
контрактными тестами. Требуются Python 3.11 и [uv](https://docs.astral.sh/uv/).

## 1. Настройка окружения

Выполните из корня репозитория:

```bash
uv sync --locked --group dev
source .venv/bin/activate
cp .env.example .env
```

В `.env` установлен `APP_LOCAL_DEVELOPMENT=true`: при запуске создаётся
`local_services/local.sqlite3` и применяется `local_services/schema.sql`.

Для глобальной БД измените флаг и укажите URL:

```bash
# .env
APP_LOCAL_DEVELOPMENT=false
```

```bash
cp config.example.yaml config.yaml
# затем укажите database.url в config.yaml
```

Если `APP_LOCAL_DEVELOPMENT` отсутствует, его значение — `false`, поэтому
`database.url` обязателен.

## 2. Запуск проекта

```bash
source .venv/bin/activate
python main.py
```

Сервис слушает `http://127.0.0.1:8080`.

```bash
curl http://127.0.0.1:8080/v1/health/ready
open http://127.0.0.1:8080/v1/docs
open http://127.0.0.1:8080/v2/docs
```

Локальной БД можно управлять отдельно:

```bash
python local_services/manage.py status
python local_services/manage.py reset
```

## 3. Проверки перед commit и push

После активации окружения установите оба Git hook:

```bash
source .venv/bin/activate
python -m pre_commit install --hook-type pre-commit
python -m pre_commit install --hook-type pre-push
```

Перед commit запускаются форматирование, линтер, mypy и тесты. Перед каждым
`git push` запускается полный `pytest`; если он завершится ошибкой, push будет
отменён.

## 4. Запуск тестов

Полный набор:

```bash
source .venv/bin/activate
python -m pytest -v
```

Проверка только локальной и глобальной конфигурации БД:

```bash
python -m pytest --no-cov -v tests/unit/test_database.py tests/unit/test_config.py
```
