"""Geometric sensor-fusion auditor: LiDAR->camera reprojection and box audits.

Implements spec section 3.1 (reprojection chain) and 3.2 (interior point
test). Boxes live in the global frame; lidar points arrive in the lidar
frame. All rigid math goes through the nuScenes devkit (`Box`,
`view_points`, `transform_matrix`) and pyquaternion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np
from nuscenes.utils.data_classes import Box
from nuscenes.utils.geometry_utils import points_in_box as nusc_points_in_box
from nuscenes.utils.geometry_utils import view_points
from pyquaternion import Quaternion

from kozquloq.auditors.base import BaseAuditor, FrameFindings
from kozquloq.constants import (
    GHOST_DISTANCE_LIMIT_M,
    GHOSTABLE_PREFIXES,
    GROUND_PLANE_Z_MAX_M,
    W_GHOST,
    W_KINEMATIC,
    W_SCALE,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from kozquloq.types import AnnBox, FrameBundle


def apply_transform(T: NDArray[np.float64], points: NDArray[np.float64]) -> NDArray[np.float64]:
    """Apply a 4x4 homogeneous transform to (N, 3) points."""
    out: NDArray[np.float64] = points @ T[:3, :3].T + T[:3, 3]
    return out


def devkit_box(box: AnnBox) -> Box:
    """Adapt our frozen AnnBox to the devkit Box (center, wlh, quaternion)."""
    return Box(
        np.asarray(box.center, dtype=np.float64),
        np.asarray(box.size, dtype=np.float64),
        Quaternion(*np.asarray(box.orientation, dtype=np.float64)),
    )


def box_corners_global(box: AnnBox) -> NDArray[np.float64]:
    """8 corner vertices of an oriented 3D box in the global frame, (8, 3)."""
    out: NDArray[np.float64] = np.asarray(devkit_box(box).corners().T, dtype=np.float64)
    return out


def points_in_box(points_xyz: NDArray[np.float64], box: AnnBox) -> NDArray[np.bool_]:
    """Interior test via the official devkit check (points are global)."""
    if len(points_xyz) == 0:
        return np.zeros(0, dtype=np.bool_)
    mask: NDArray[np.bool_] = nusc_points_in_box(devkit_box(box), points_xyz.T)
    return mask


def _lidar_to_camera_matrix(bundle: FrameBundle) -> NDArray[np.float64]:
    """Full chain lidar -> ego -> global -> ego(t_cam) -> camera (spec 3.1)."""
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
    with np.errstate(divide="ignore", invalid="ignore"):
        uv = view_points(pts_cam.T, bundle.K, normalize=True).T[:, :2]
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
    with np.errstate(divide="ignore", invalid="ignore"):
        uv = view_points(pts_cam.T, bundle.K, normalize=True).T[:, :2]
    return uv, z


def is_ghostable(category: str) -> bool:
    """Ghost checks apply to rigid/movable categories only."""
    return category.startswith(GHOSTABLE_PREFIXES)


@dataclass
class BoxAuditResult:
    annotation_token: str
    instance_token: str
    category: str
    distance_to_ego_m: float
    lidar_point_count: int
    radar_return_count: int
    is_ghost: bool
    is_visible_on_camera: bool
    center_global: NDArray[np.float64] = field(repr=False)
    volume_m3: float = 0.0
    velocity_mps: float | None = None
    acceleration_mps2: float | None = None
    volume_variance_ratio: float | None = None
    is_kinematic_outlier: bool = False
    is_scale_unstable: bool = False
    severity: float = 0.0

    @property
    def flagged(self) -> bool:
        return self.is_ghost or self.is_kinematic_outlier or self.is_scale_unstable

    def finalize_severity(self) -> None:
        score = (
            W_GHOST * self.is_ghost
            + W_KINEMATIC * self.is_kinematic_outlier
            + W_SCALE * self.is_scale_unstable
        )
        self.severity = round(min(1.0, score), 4)

    def to_row(self, sample_token: str) -> dict[str, Any]:
        return {
            "annotation_token": self.annotation_token,
            "sample_token": sample_token,
            "instance_token": self.instance_token,
            "category": self.category,
            "distance_to_ego_m": round(float(self.distance_to_ego_m), 4),
            "lidar_points": int(self.lidar_point_count),
            "radar_return_count": int(self.radar_return_count),
            "is_ghost": self.is_ghost,
            "is_visible_on_camera": self.is_visible_on_camera,
            "velocity_mps": self.velocity_mps,
            "acceleration_mps2": self.acceleration_mps2,
            "volume_variance_ratio": self.volume_variance_ratio,
            "is_kinematic_outlier": self.is_kinematic_outlier,
            "is_scale_unstable": self.is_scale_unstable,
            "severity": self.severity,
        }


def audit_frame_geometry(bundle: FrameBundle) -> list[BoxAuditResult]:
    """Audit every annotation box of one frame against the lidar cloud."""
    _, _, _, pts_global = project_lidar_to_camera(bundle)
    # Ground plane isolation: drop returns below the lidar origin plane so
    # road surface points can never leak into box occupancy counts.
    pts_global = pts_global[bundle.lidar_points[:, 2] >= GROUND_PLANE_Z_MAX_M]
    h, w = bundle.image.shape[:2]

    results = []
    for box in bundle.boxes:
        n_points = int(points_in_box(pts_global, box).sum())

        center_ego_cam = apply_transform(
            np.linalg.inv(bundle.T_ego_cam_to_global), box.center[None]
        )[0]
        distance = float(np.linalg.norm(center_ego_cam))

        uv, depth = project_corners_to_camera(bundle, box_corners_global(box))
        center_uv = uv.mean(axis=0)
        visible = bool((depth > 0.1).any() and 0 <= center_uv[0] < w and 0 <= center_uv[1] < h)

        is_ghost = (
            is_ghostable(box.category) and n_points == 0 and distance < GHOST_DISTANCE_LIMIT_M
        )
        results.append(
            BoxAuditResult(
                annotation_token=box.token,
                instance_token=box.instance_token,
                category=box.category,
                distance_to_ego_m=distance,
                lidar_point_count=n_points,
                radar_return_count=box.radar_returns,
                is_ghost=is_ghost,
                is_visible_on_camera=visible,
                center_global=box.center,
                volume_m3=float(np.prod(box.size)),
            )
        )
    return results


class GeometricAuditor(BaseAuditor):
    """LiDAR->camera reprojection + box occupancy audit (spec 3.1, 3.2)."""

    def audit_sample(self, bundle: FrameBundle, findings: FrameFindings) -> None:
        findings.boxes = audit_frame_geometry(bundle)
