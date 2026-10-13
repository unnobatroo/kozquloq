"""Analytical queries over the quality store."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kozquloq.storage.base import AuditStore


def slice_failure_rates(store: AuditStore) -> list[dict[str, Any]]:
    return store.query("SELECT * FROM view_slice_failure_rates ORDER BY failure_rate_pct DESC")


def worst_samples(store: AuditStore, n: int = 5) -> list[dict[str, Any]]:
    return store.query(
        """
        SELECT s.sample_token, s.scene_token, s.timestamp, s.ego_speed_mps,
               s.has_geometric_drift,
               COUNT(a.annotation_token) AS n_annotations,
               SUM(CASE WHEN a.is_ghost_label THEN 1 ELSE 0 END) AS ghosts,
               SUM(CASE WHEN a.is_kinematic_outlier THEN 1 ELSE 0 END) AS kinematic_outliers,
               ROUND(MAX(a.severity_score), 3) AS max_severity
        FROM samples s
        JOIN annotation_audits a ON a.sample_token = s.sample_token
        GROUP BY s.sample_token, s.scene_token, s.timestamp, s.ego_speed_mps, s.has_geometric_drift
        ORDER BY max_severity DESC, ghosts DESC
        LIMIT ?
        """,
        [n],
    )


def health_summary(store: AuditStore) -> dict[str, Any]:
    row = store.query(
        """
        SELECT COUNT(DISTINCT s.sample_token) AS frames,
               COUNT(a.annotation_token) AS annotations,
               SUM(CASE WHEN a.is_ghost_label THEN 1 ELSE 0 END) AS ghosts,
               SUM(CASE WHEN a.is_kinematic_outlier THEN 1 ELSE 0 END) AS kinematic_outliers,
               SUM(CASE WHEN a.is_scale_unstable THEN 1 ELSE 0 END) AS scale_unstable,
               COUNT(DISTINCT CASE WHEN s.camera_underexposed_count > 0 THEN s.sample_token END)
                   AS underexposed_frames,
               COUNT(DISTINCT CASE WHEN s.has_geometric_drift THEN s.sample_token END)
                   AS drift_frames
        FROM samples s
        LEFT JOIN annotation_audits a ON a.sample_token = s.sample_token
        """
    )[0]
    annotations = row["annotations"] or 0
    flagged = (row["ghosts"] or 0) + (row["kinematic_outliers"] or 0)
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


def sample_images(store: AuditStore, sample_token: str) -> dict[str, bytes]:
    rows = store.query(
        "SELECT variant, jpeg FROM sample_images WHERE sample_token = ?",
        [sample_token],
    )
    return {r["variant"]: r["jpeg"] for r in rows}
