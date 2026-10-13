"""Frame-level sensor health: exposure, return counts, geometric drift."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from kozquloq.auditors.base import BaseAuditor, FrameFindings
from kozquloq.auditors.geometry import (
    BoxAuditResult,
    box_corners_global,
    project_corners_to_camera,
    project_lidar_to_camera,
)
from kozquloq.constants import UNDEREXPOSED_MEAN_INTENSITY

if TYPE_CHECKING:
    from kozquloq.types import FrameBundle, SceneMeta


@dataclass
class SampleHealth:
    camera_underexposed_count: int
    lidar_total_points: int
    radar_total_returns: int
    has_geometric_drift: bool

    def to_row(self, bundle: FrameBundle, scene: SceneMeta) -> dict[str, Any]:
        return {
            "sample_token": bundle.sample_token,
            "scene_name": scene.name,
            "weather": scene.weather,
            "time_of_day": scene.time_of_day,
            "timestamp": int(bundle.timestamp_us),
            "ego_speed_mps": float(bundle.ego_speed_mps),
            "camera_underexposed_count": self.camera_underexposed_count,
            "lidar_total_points": self.lidar_total_points,
            "radar_total_returns": self.radar_total_returns,
            "has_geometric_drift": self.has_geometric_drift,
        }


def audit_sample_health(bundle: FrameBundle, box_results: list[BoxAuditResult]) -> SampleHealth:
    underexposed = int(bundle.image.mean() < UNDEREXPOSED_MEAN_INTENSITY)

    # Geometric drift heuristic: a visible box has plenty of 3D lidar hits but
    # almost no projected points land inside its 2D footprint -> miscalibration.
    uv, _, in_image, _ = project_lidar_to_camera(bundle)
    h, w = bundle.image.shape[:2]
    in_img_uv = uv[in_image]
    drift = False
    for box, result in zip(bundle.boxes, box_results, strict=False):
        if not (result.is_visible_on_camera and result.lidar_point_count > 20):
            continue
        corners_uv, _ = project_corners_to_camera(bundle, box_corners_global(box))
        x0, y0 = np.clip(corners_uv.min(axis=0), [0, 0], [w, h])
        x1, y1 = np.clip(corners_uv.max(axis=0), [0, 0], [w, h])
        hits = int(
            (
                (in_img_uv[:, 0] >= x0)
                & (in_img_uv[:, 0] <= x1)
                & (in_img_uv[:, 1] >= y0)
                & (in_img_uv[:, 1] <= y1)
            ).sum()
        )
        if hits < 3:
            drift = True
            break

    return SampleHealth(
        camera_underexposed_count=underexposed,
        lidar_total_points=len(bundle.lidar_points),
        radar_total_returns=bundle.radar_total_returns,
        has_geometric_drift=drift,
    )


class SensorHealthAuditor(BaseAuditor):
    """Frame-level sensor health: exposure, return counts, geometric drift."""

    def audit_sample(self, bundle: FrameBundle, findings: FrameFindings) -> None:
        findings.health = audit_sample_health(bundle, findings.boxes)
