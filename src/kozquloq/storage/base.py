"""Storage abstraction: the pipeline talks to `AuditStore`, not DuckDB."""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

    from numpy.typing import NDArray


class AuditStore(ABC):
    """Persistence contract for audit metrics (samples/audits)."""

    @abstractmethod
    def save_sample(self, row: dict[str, Any]) -> None: ...

    @abstractmethod
    def save_audits(self, rows: list[dict[str, Any]]) -> None: ...

    @abstractmethod
    def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]: ...

    @abstractmethod
    def query_numpy(self, sql: str, params: list[Any] | None = None) -> dict[str, NDArray[Any]]: ...

    @abstractmethod
    def get_slice_metrics(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def get_summary(self) -> dict[str, Any]: ...

    @abstractmethod
    def get_invalid_tokens(self, min_severity: float = 0.5) -> list[dict[str, Any]]: ...

    @abstractmethod
    def export_parquet(self, out_path: str, min_severity: float = 0.5) -> None: ...

    @abstractmethod
    def clear(self) -> None: ...

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Atomic write scope: commits on success, rolls back on error.

        Default is a no-op for stores without transaction support.
        """
        yield
