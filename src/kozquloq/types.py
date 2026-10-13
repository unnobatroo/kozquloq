"""Shared intermediate representation between ingestion, auditors and storage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray


@dataclass(frozen=True)
class AnnBox:
    """A 3D annotation box in the global frame (nuScenes convention)."""

    token: str
    instance_token: str
    category: str
    center: NDArray[np.float64]  # (3,) global xyz
    size: NDArray[np.float64]  # (3,) w, l, h
    orientation: NDArray[np.float64]  # (4,) quaternion w, x, y, z
    radar_returns: int = 0


@dataclass(frozen=True)
class FrameBundle:
    """Everything auditors need for one keyframe.

    Transforms are 4x4 homogeneous matrices following spec §3.1:
      T_lidar_to_ego          sensor calibration (lidar -> ego)
      T_ego_lidar_to_global   ego pose at lidar timestamp
      T_ego_cam_to_global     ego pose at camera timestamp
      T_cam_to_ego            camera calibration (cam -> ego)
    """

    sample_token: str
    scene_token: str
    timestamp_us: int
    ego_speed_mps: float
    image: NDArray[np.uint8]  # H x W x 3, RGB
    lidar_points: NDArray[np.float64]  # (N, 3) in lidar frame
    radar_total_returns: int
    boxes: list[AnnBox]
    T_lidar_to_ego: NDArray[np.float64]
    T_ego_lidar_to_global: NDArray[np.float64]
    T_ego_cam_to_global: NDArray[np.float64]
    T_cam_to_ego: NDArray[np.float64]
    K: NDArray[np.float64]  # (3, 3) camera intrinsics


@dataclass(frozen=True)
class SceneMeta:
    token: str
    name: str
    description: str
    weather: str
    time_of_day: str
