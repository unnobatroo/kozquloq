"""PyTorch quality-masked dataset over the DuckDB audit tables.

Each item is one audited annotation: engineered features, a corruption label
(ghost or kinematic outlier), and a sample weight for loss downweighting.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

import numpy as np
import torch
from torch.utils.data import Dataset

from kozquloq.storage.duckdb_store import Store


class QualityItem(TypedDict):
    features: torch.Tensor
    label: torch.Tensor
    weight: torch.Tensor
    sample_token: str
    annotation_token: str
    severity: float


if TYPE_CHECKING:
    from collections.abc import Callable

FEATURE_COLUMNS = [
    "distance_to_ego_m",
    "lidar_point_count",
    "radar_return_count",
    "velocity_mps",
    "acceleration_mps2",
    "volume_variance_ratio",
]


def _features(row: dict[str, Any]) -> list[float]:
    return [
        float(row["distance_to_ego_m"]),
        float(np.log1p(row["lidar_point_count"])),
        float(row["radar_return_count"]),
        float(row["velocity_mps"] or 0.0),
        float(row["acceleration_mps2"] or 0.0),
        float(row["volume_variance_ratio"] or 0.0),
    ]


class QualityAuditDataset(Dataset[QualityItem]):
    def __init__(
        self,
        db_path: str,
        min_severity_to_keep: float = 0.5,
        drop: bool = False,
        transform: Callable[[torch.Tensor], torch.Tensor] | None = None,
    ) -> None:
        """min_severity_to_keep: audits at/above this severity get weight 0
        (downweighted) or are removed entirely when drop=True."""
        with Store(db_path) as store:
            self._rows = store.query("SELECT * FROM annotation_audits")
        if drop:
            self._rows = [r for r in self._rows if r["severity_score"] < min_severity_to_keep]
        self._min_sev = min_severity_to_keep
        self._transform = transform

    def __len__(self) -> int:
        return len(self._rows)

    def __getitem__(self, idx: int) -> QualityItem:
        row = self._rows[idx]
        feats = torch.tensor(_features(row), dtype=torch.float32)
        if self._transform:
            feats = self._transform(feats)
        label = torch.tensor(
            1 if (row["is_ghost_label"] or row["is_kinematic_outlier"]) else 0,
            dtype=torch.long,
        )
        severity = float(row["severity_score"])
        weight = 0.0 if severity >= self._min_sev else max(0.05, 1.0 - severity)
        return {
            "features": feats,
            "label": label,
            "weight": torch.tensor(weight, dtype=torch.float32),
            "sample_token": row["sample_token"],
            "annotation_token": row["annotation_token"],
            "severity": severity,
        }
