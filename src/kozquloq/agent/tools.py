"""Structured SQL tools the diagnostic agent can call."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from kozquloq.storage import views

if TYPE_CHECKING:
    from kozquloq.storage.duckdb_store import Store

# Word-boundary blocklist for anything that can mutate state or touch the FS.
_WRITE_RE = re.compile(
    r"\b(insert|update|delete|drop|create|alter|attach|detach|copy|export|import|"
    r"pragma|install|load|call|set|use|truncate|replace|grant|revoke|vacuum)\b",
    re.IGNORECASE,
)


class AuditTools:
    def __init__(self, store: Store) -> None:
        self.store = store
        self.calls: list[str] = []

    def tool_specs(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "health_summary",
                "description": "Overall dataset health: frames, flagged counts, failure %, grade",
                "params": {},
            },
            {
                "name": "slice_failures",
                "description": "Failure rates grouped by weather, time of day, category",
                "params": {},
            },
            {
                "name": "worst_samples",
                "description": "Top-N most anomalous frames",
                "params": {"n": "int"},
            },
            {
                "name": "category_breakdown",
                "description": "Flag counts per annotation category",
                "params": {},
            },
            {
                "name": "run_sql",
                "description": "Read-only SQL against the audit tables",
                "params": {"sql": "str"},
            },
        ]

    def dispatch(self, name: str, args: dict[str, Any] | None = None) -> Any:
        args = args or {}
        self.calls.append(name)
        if name == "health_summary":
            return views.health_summary(self.store)
        if name == "slice_failures":
            return views.slice_failure_rates(self.store)
        if name == "worst_samples":
            return views.worst_samples(self.store, int(args.get("n", 5)))
        if name == "category_breakdown":
            return self.store.query(
                """
                SELECT category, COUNT(*) AS n,
                       SUM(CASE WHEN is_ghost_label THEN 1 ELSE 0 END) AS ghosts,
                       SUM(CASE WHEN is_kinematic_outlier THEN 1 ELSE 0 END) AS kin_outliers,
                       ROUND(AVG(severity_score), 3) AS avg_severity
                FROM annotation_audits GROUP BY category ORDER BY avg_severity DESC
                """
            )
        if name == "run_sql":
            sql = str(args.get("sql", "")).strip().rstrip(";").strip()
            if (
                ";" in sql
                or not sql.upper().startswith(("SELECT", "WITH"))
                or _WRITE_RE.search(sql)
            ):
                raise ValueError("run_sql accepts a single read-only SELECT/WITH query")
            return self.store.query(sql)
        raise ValueError(f"unknown tool: {name}")
