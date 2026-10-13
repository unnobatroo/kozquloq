"""Geometric sensor-fusion auditor: LiDAR->camera reprojection and box audits.

Implements spec §3.1 (reprojection chain) and §3.2 (interior point test).
Boxes live in the global frame; lidar points arrive in the lidar frame.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import TYPE_CHECKING, Any

import numpy as np

from kozquloq.auditors.base import BaseAuditor, FrameFindings
from kozquloq.constants import (
    GHOST_DISTANCE_LIMIT_M,
    W_GHOST,
    W_KINEMATIC,
    W_SCALE,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from kozquloq.types import AnnBox, FrameBundle


def quat_to_rot(q: NDArray[np.float64]) -> NDArray[np.float64]:
    """Quaternion (w, x, y, z) -> 3x3 rotation matrix."""
    w, x, y, z = q / np.linalg.norm(q)
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def apply_transform(T: NDArray[np.float64], points: NDArray[np.float64]) -> NDArray[np.float64]:
    """Apply a 4x4 homogeneous transform to (N, 3) points."""
    out: NDArray[np.float64] = points @ T[:3, :3].T + T[:3, 3]
    return out


def _half_extents(box: AnnBox) -> NDArray[np.float64]:
    # nuScenes local box frame: x = length (heading), y = width, z = height.
    # size is stored (w, l, h), so local half-extents are (l, w, h) / 2.
    return box.size[[1, 0, 2]] / 2.0


def box_corners_global(box: AnnBox) -> NDArray[np.float64]:
    """8 corner vertices of an oriented 3D box in the global frame."""
    local = np.array(list(product([-1.0, 1.0], repeat=3))) * _half_extents(box)
    return local @ quat_to_rot(box.orientation).T + box.center


def points_in_box(points_xyz: NDArray[np.float64], box: AnnBox) -> NDArray[np.bool_]:
    """Interior test: express points in the box frame, bound by half-extents."""
    if len(points_xyz) == 0:
        return np.zeros(0, dtype=np.bool_)
    local = (points_xyz - box.center) @ quat_to_rot(box.orientation)
    mask: NDArray[np.bool_] = (np.abs(local) <= _half_extents(box)).all(axis=1)
    return mask


def _lidar_to_camera_matrix(bundle: FrameBundle) -> NDArray[np.float64]:
    """Full chain lidar -> ego -> global -> ego(t_cam) -> camera (spec §3.1)."""
    T_global_to_ego_cam = np.linalg.inv(bundle.T_ego_cam_to_global)
    T_ego_to_cam = np.linalg.inv(bundle.T_cam_to_ego)
    return T_ego_to_cam @ T_global_to_ego_cam @ bundle.T_ego_lidar_to_global @ bundle.T_lidar_to_ego


def project_lidar_to_camera(
    bundle: FrameBundle,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.bool_], NDArray[np.float64]]:
    """Project lidar points onto the image plane.

    Returns (uv (N,2), depth (N,), in_image (N,), points_global (N,3)).
    """
    pts_cam = apply_transform(_lidar_to_camera_matrix(bundle), bundle.lidar_points)
    pts_global = apply_transform(
        bundle.T_ego_lidar_to_global @ bundle.T_lidar_to_ego, bundle.lidar_points
    )
    z = pts_cam[:, 2]
    in_front = z > 0.1
    safe_z = np.where(in_front, z, 1.0)
    uv = (bundle.K @ pts_cam.T).T[:, :2] / safe_z[:, None]
    h, w = bundle.image.shape[:2]
    in_image = in_front & (uv[:, 0] >= 0) & (uv[:, 0] < w) & (uv[:, 1] >= 0) & (uv[:, 1] < h)
    return uv, z, in_image, pts_global


def project_corners_to_camera(
    bundle: FrameBundle, corners_global: NDArray[np.float64]
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Project 8 global box corners to image uv. Returns (8,2) uv and (8,) depth."""
    T_global_to_cam = np.linalg.inv(bundle.T_cam_to_ego) @ np.linalg.inv(bundle.T_ego_cam_to_global)
    pts_cam = apply_transform(T_global_to_cam, corners_global)
    z = pts_cam[:, 2]
    safe_z = np.where(z > 0.1, z, 1.0)
    uv = (bundle.K @ pts_cam.T).T[:, :2] / safe_z[:, None]
    return uv, z


@dataclass
class BoxAuditResult:
    annotation_token: str
    instance_token: str
    category: str
    distance_to_ego_m: float
    lidar_point_count: int
    radar_return_count: int
    is_ghost_label: bool
    is_visible_on_camera: bool
    center_global: NDArray[np.float64] = field(repr=False)
    volume_m3: float = 0.0
    velocity_mps: float | None = None
    acceleration_mps2: float | None = None
    volume_variance_ratio: float | None = None
    is_kinematic_outlier: bool = False
    is_scale_unstable: bool = False
    severity_score: float = 0.0

    @property
    def flagged(self) -> bool:
        return self.is_ghost_label or self.is_kinematic_outlier or self.is_scale_unstable

    def finalize_severity(self) -> None:
        score = (
            W_GHOST * self.is_ghost_label
            + W_KINEMATIC * self.is_kinematic_outlier
            + W_SCALE * self.is_scale_unstable
        )
        self.severity_score = round(min(1.0, score), 4)

    def to_row(self, sample_token: str) -> dict[str, Any]:
        return {
            "annotation_token": self.annotation_token,
            "sample_token": sample_token,
            "instance_token": self.instance_token,
            "category": self.category,
            "distance_to_ego_m": round(float(self.distance_to_ego_m), 4),
            "lidar_point_count": int(self.lidar_point_count),
            "radar_return_count": int(self.radar_return_count),
            "is_ghost_label": self.is_ghost_label,
            "is_visible_on_camera": self.is_visible_on_camera,
            "velocity_mps": self.velocity_mps,
            "acceleration_mps2": self.acceleration_mps2,
            "volume_variance_ratio": self.volume_variance_ratio,
            "is_kinematic_outlier": self.is_kinematic_outlier,
            "is_scale_unstable": self.is_scale_unstable,
            "severity_score": self.severity_score,
        }


def audit_frame_geometry(bundle: FrameBundle) -> list[BoxAuditResult]:
    """Audit every annotation box of one frame against the lidar cloud."""
    _, _, _, pts_global = project_lidar_to_camera(bundle)
    h, w = bundle.image.shape[:2]

    results = []
    for box in bundle.boxes:
        inside = points_in_box(pts_global, box)
        n_points = int(inside.sum())

        center_ego_cam = apply_transform(
            np.linalg.inv(bundle.T_ego_cam_to_global), box.center[None]
        )[0]
        distance = float(np.linalg.norm(center_ego_cam))

        uv, depth = project_corners_to_camera(bundle, box_corners_global(box))
        center_uv = uv.mean(axis=0)
        visible = bool((depth > 0.1).any() and 0 <= center_uv[0] < w and 0 <= center_uv[1] < h)

        is_ghost = n_points == 0 and distance <= GHOST_DISTANCE_LIMIT_M
        results.append(
            BoxAuditResult(
                annotation_token=box.token,
                instance_token=box.instance_token,
                category=box.category,
                distance_to_ego_m=distance,
                lidar_point_count=n_points,
                radar_return_count=box.radar_returns,
                is_ghost_label=is_ghost,
                is_visible_on_camera=visible,
                center_global=box.center,
                volume_m3=float(np.prod(box.size)),
            )
        )
    return results


class GeometricAuditor(BaseAuditor):
    """LiDAR->camera reprojection + box occupancy audit (spec §3.1, §3.2)."""

    def audit_sample(self, bundle: FrameBundle, findings: FrameFindings) -> None:
        findings.boxes = audit_frame_geometry(bundle)
