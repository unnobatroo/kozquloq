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

    import pyarrow as pa


class DuckDBAuditStore(AuditStore):
    """DuckDB-backed AuditStore."""

    def __init__(self, path: str = ":memory:") -> None:
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.con = duckdb.connect(path)
        self.con.execute(resources.files("kozquloq.storage").joinpath("schema.sql").read_text())

    # --- AuditStore API -----------------------------------------------------

    def save_sample(self, row: dict[str, Any]) -> None:
        self.insert_many("samples", [row])

    def save_audits(self, rows: list[dict[str, Any]]) -> None:
        self.insert_many("audits", rows)

    def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        cur = self.con.execute(sql, params or [])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]

    def query_arrow(self, sql: str, params: list[Any] | None = None) -> pa.Table:
        """Columnar read for zero-copy consumers (torch dataset, parquet)."""
        return self.con.execute(sql, params or []).to_arrow_table()

    def get_slice_metrics(self) -> list[dict[str, Any]]:
        return self.query("SELECT * FROM view_slice_failure_rates ORDER BY failure_rate_pct DESC")

    def get_summary(self) -> dict[str, Any]:
        row = self.query(
            """
            SELECT COUNT(DISTINCT s.sample_token) AS frames,
                   COUNT(a.annotation_token) AS annotations,
                   SUM(CASE WHEN a.is_ghost THEN 1 ELSE 0 END) AS ghosts,
                   SUM(CASE WHEN a.is_kinematic_outlier THEN 1 ELSE 0 END) AS kinematic_outliers,
                   SUM(CASE WHEN a.is_scale_unstable THEN 1 ELSE 0 END) AS scale_unstable,
                   COUNT(DISTINCT CASE WHEN s.camera_underexposed_count > 0
                        THEN s.sample_token END) AS underexposed_frames,
                   COUNT(DISTINCT CASE WHEN s.has_geometric_drift
                        THEN s.sample_token END) AS drift_frames
            FROM samples s
            LEFT JOIN audits a ON a.sample_token = s.sample_token
            """
        )[0]
        annotations = row["annotations"] or 0
        flagged = (
            (row["ghosts"] or 0) + (row["kinematic_outliers"] or 0) + (row["scale_unstable"] or 0)
        )
        failure_pct = round(100.0 * flagged / annotations, 2) if annotations else 0.0
        grade = (
            "A"
            if failure_pct < 2
            else "B"
            if failure_pct < 5
            else "C"
            if failure_pct < 10
            else "D"
            if failure_pct < 20
            else "F"
        )
        return {**row, "flagged": flagged, "failure_pct": failure_pct, "grade": grade}

    def get_invalid_tokens(self, min_severity: float = 0.5) -> list[dict[str, Any]]:
        """Annotation tokens to mask out of training, with a human reason."""
        return self.query(
            """
            SELECT annotation_token, category, severity,
                   CASE
                       WHEN is_ghost THEN 'ghost: zero lidar returns inside box'
                       WHEN is_kinematic_outlier THEN 'kinematic: non-physical motion'
                       WHEN is_scale_unstable THEN 'scale: volume changed between frames'
                       ELSE 'flagged'
                   END AS reason
            FROM audits
            WHERE severity >= ?
            ORDER BY severity DESC, annotation_token
            """,
            [min_severity],
        )

    def clear(self) -> None:
        """Delete all rows (children first) for a clean re-audit."""
        for table in ("audits", "samples"):
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

    def export_parquet(self, out_path: str) -> None:
        self.con.execute("COPY audits TO ? (FORMAT PARQUET)", [out_path])

    def close(self) -> None:
        self.con.close()

    def __enter__(self) -> DuckDBAuditStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


# Backward-compatible alias
Store = DuckDBAuditStore
