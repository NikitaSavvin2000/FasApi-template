FROM python:3.11.11-slim-bookworm AS builder

ARG UV_VERSION=0.12.21
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1
WORKDIR /app

RUN pip install --no-cache-dir "uv==${UV_VERSION}"
COPY pyproject.toml uv.lock README.md main.py ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
COPY local_services ./local_services
RUN uv sync --locked --no-dev --no-editable

FROM python:3.11.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:${PATH}"
WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --create-home app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src
COPY --from=builder --chown=app:app /app/local_services /app/local_services
COPY --from=builder --chown=app:app /app/main.py /app/main.py

USER app
EXPOSE 8080
ENTRYPOINT ["python", "main.py"]
