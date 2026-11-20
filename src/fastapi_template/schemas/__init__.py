"""Pydantic-схемы, определяющие публичный HTTP API."""

from .examples import ProcessRequest, ProcessResponse
from .health import HealthResponse

__all__ = ["HealthResponse", "ProcessRequest", "ProcessResponse"]
