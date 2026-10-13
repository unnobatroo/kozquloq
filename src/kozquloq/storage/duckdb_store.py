"""DuckDB columnar quality store: schema init, batch inserts, queries."""

from __future__ import annotations

import os
from contextlib import contextmanager
from importlib import resources
from typing import TYPE_CHECKING, Any

import duckdb

from kozquloq.storage.base import AuditStore

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator


class DuckDBAuditStore(AuditStore):
    """DuckDB-backed AuditStore."""

    def __init__(self, path: str = ":memory:") -> None:
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.con = duckdb.connect(path)
        self.con.execute(resources.files("kozquloq.storage").joinpath("schema.sql").read_text())

    # --- AuditStore API -----------------------------------------------------

    def save_scene(self, row: dict[str, Any]) -> None:
        self.insert_many("scenes", [row])

    def save_sample(self, row: dict[str, Any]) -> None:
        self.insert_many("samples", [row])

    def save_audit_results(self, rows: list[dict[str, Any]]) -> None:
        self.insert_many("annotation_audits", rows)

    def save_image(self, sample_token: str, variant: str, jpeg: bytes) -> None:
        self.con.execute(
            "INSERT OR REPLACE INTO sample_images VALUES (?, ?, ?)",
            [sample_token, variant, jpeg],
        )

    def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        cur = self.con.execute(sql, params or [])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]

    def query_slice(self) -> list[dict[str, Any]]:
        from kozquloq.storage import views

        return views.slice_failure_rates(self)

    def get_summary(self) -> dict[str, Any]:
        from kozquloq.storage import views

        return views.health_summary(self)

    def clear(self) -> None:
        """Delete all rows (children first) for a clean re-audit."""
        for table in ("sample_images", "annotation_audits", "samples", "scenes"):
            self.con.execute(f"DELETE FROM {table}")

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self.con.begin()
        try:
            yield
        except BaseException:
            self.con.rollback()
            raise
        self.con.commit()

    # --- convenience API ----------------------------------------------------

    def insert_many(self, table: str, rows: Iterable[dict[str, Any]]) -> None:
        rows = list(rows)
        if not rows:
            return
        cols = list(rows[0].keys())
        placeholders = ", ".join("?" for _ in cols)
        sql = f"INSERT OR REPLACE INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
        self.con.executemany(sql, [[r.get(c) for c in cols] for r in rows])

    def export_parquet(self, out_dir: str) -> None:
        os.makedirs(out_dir, exist_ok=True)
        for table in ("scenes", "samples", "annotation_audits"):
            self.con.execute(f"COPY {table} TO '{out_dir}/{table}.parquet' (FORMAT PARQUET)")

    def close(self) -> None:
        self.con.close()

    def __enter__(self) -> DuckDBAuditStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


# Backward-compatible alias
Store = DuckDBAuditStore
