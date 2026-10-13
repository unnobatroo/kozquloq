"""PyTorch quality-masked dataset over the DuckDB audit tables.

Each item is one audited annotation: engineered features, a corruption label
(ghost or kinematic outlier), and a sample weight for loss downweighting.
Rows are loaded via a columnar Arrow read and stacked into tensors directly,
not per-row dict conversion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

import numpy as np
import torch
from torch.utils.data import Dataset

from kozquloq.storage.duckdb_store import Store

if TYPE_CHECKING:
    import pyarrow as pa
    from numpy.typing import NDArray


class QualityItem(TypedDict):
    features: torch.Tensor
    label: torch.Tensor
    weight: torch.Tensor
    sample_token: str
    annotation_token: str
    severity: float


FEATURE_COLUMNS = [
    "distance_to_ego_m",
    "lidar_points",
    "radar_return_count",
    "velocity_mps",
    "acceleration_mps2",
    "volume_variance_ratio",
]


def _col(table: pa.Table, name: str) -> NDArray[np.float64]:
    """One column as a float64 numpy array; SQL NULLs become NaN."""
    arr = table.column(name).combine_chunks()
    out: NDArray[np.float64] = arr.to_numpy(zero_copy_only=False).astype(np.float64)
    return out


class QualityAuditDataset(Dataset[QualityItem]):
    def __init__(self, db_path: str, min_severity_to_keep: float = 0.5, drop: bool = False) -> None:
        """min_severity_to_keep: audits at/above this severity get weight 0
        (downweighted) or are removed entirely when drop=True."""
        with Store(db_path) as store:
            table = store.query_arrow(
                """
                SELECT annotation_token, sample_token, distance_to_ego_m,
                       lidar_points, radar_return_count, velocity_mps,
                       acceleration_mps2, volume_variance_ratio,
                       is_ghost, is_kinematic_outlier, severity
                FROM audits
                """
            )

        feats = np.stack(
            [
                _col(table, "distance_to_ego_m"),
                np.log1p(_col(table, "lidar_points")),
                _col(table, "radar_return_count"),
                _col(table, "velocity_mps"),
                _col(table, "acceleration_mps2"),
                _col(table, "volume_variance_ratio"),
            ],
            axis=1,
        )
        feats = np.nan_to_num(feats, nan=0.0)
        labels = np.logical_or(_col(table, "is_ghost"), _col(table, "is_kinematic_outlier")).astype(
            np.int64
        )
        severity = _col(table, "severity")

        keep = np.arange(len(severity))
        if drop:
            keep = np.nonzero(severity < min_severity_to_keep)[0]
        self._features = torch.from_numpy(feats[keep].astype(np.float32))
        self._labels = torch.from_numpy(labels[keep])
        self._severity = severity[keep]
        self._sample_tokens = table.column("sample_token").to_pylist()
        self._annotation_tokens = table.column("annotation_token").to_pylist()
        self._keep = keep
        self._min_sev = min_severity_to_keep

    def __len__(self) -> int:
        return len(self._features)

    def __getitem__(self, idx: int) -> QualityItem:
        severity = float(self._severity[idx])
        weight = 0.0 if severity >= self._min_sev else max(0.05, 1.0 - severity)
        return {
            "features": self._features[idx],
            "label": self._labels[idx],
            "weight": torch.tensor(weight, dtype=torch.float32),
            "sample_token": self._sample_tokens[int(self._keep[idx])],
            "annotation_token": self._annotation_tokens[int(self._keep[idx])],
            "severity": severity,
        }
