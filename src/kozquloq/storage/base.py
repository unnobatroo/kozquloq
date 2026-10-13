"""Storage abstraction: the pipeline talks to `AuditStore`, not DuckDB."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AuditStore(ABC):
    """Persistence contract for audit metrics (scenes/samples/audits/images)."""

    @abstractmethod
    def save_scene(self, row: dict[str, Any]) -> None: ...

    @abstractmethod
    def save_sample(self, row: dict[str, Any]) -> None: ...

    @abstractmethod
    def save_audit_results(self, rows: list[dict[str, Any]]) -> None: ...

    @abstractmethod
    def save_image(self, sample_token: str, variant: str, jpeg: bytes) -> None: ...

    @abstractmethod
    def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]: ...

    @abstractmethod
    def query_slice(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def get_summary(self) -> dict[str, Any]: ...

    @abstractmethod
    def clear(self) -> None: ...
