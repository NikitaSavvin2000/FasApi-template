-- Базовый шаблон локальной SQLite БД.
-- Добавляйте прикладные таблицы отдельными миграциями, сохраняя идемпотентность.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_versions (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS example_records (
    id INTEGER PRIMARY KEY,
    value TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_example_records_created_at
    ON example_records (created_at);
