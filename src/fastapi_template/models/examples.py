"""Доменные значения, используемые демонстрационными сервисами."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProcessedText:
    value: str
    repetitions: int
