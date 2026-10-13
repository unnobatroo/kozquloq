"""Synthetic multi-frame scene fixture.

Produces deterministic FrameBundles with known calibrations, a moving vehicle,
ground-plane lidar returns, and injected faults (ghost label, acceleration
spike, volume drift, underexposed frame) so audits have anomalies to find.
Used by `kozquloq demo`, tests, and scripts/seed_synthetic_fixtures.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from pyquaternion import Quaternion

from kozquloq.types import AnnBox, FrameBundle, SceneMeta

if TYPE_CHECKING:
    from numpy.typing import NDArray

IMG_W, IMG_H = 640, 360
K_MATRIX = np.array([[800.0, 0.0, 320.0], [0.0, 800.0, 180.0], [0.0, 0.0, 1.0]])

# cam axes: x right, y down, z forward; ego: x fwd, y left, z up
_R_CAM_EGO = np.array([[0.0, -1.0, 0.0], [0.0, 0.0, -1.0], [1.0, 0.0, 0.0]])
T_CAM_TO_EGO = np.eye(4)
T_CAM_TO_EGO[:3, :3] = _R_CAM_EGO.T

DT_S = 0.5  # 2 Hz keyframes
EGO_SPEED_MPS = 4.0
CAR_SPEED_MPS = 6.0


def _transform(t: NDArray[np.float64], R: NDArray[np.float64] | None = None) -> NDArray[np.float64]:
    T = np.eye(4)
    T[:3, :3] = np.eye(3) if R is None else R
    T[:3, 3] = t
    return T


def _yaw_quat(yaw: float) -> NDArray[np.float64]:
    return np.array([np.cos(yaw / 2), 0.0, 0.0, np.sin(yaw / 2)])


def _box_points_in_lidar(
    rng: np.random.Generator,
    center: NDArray[np.float64],
    size: NDArray[np.float64],
    yaw: float,
    T_global_to_lidar: NDArray[np.float64],
    n: int = 400,
) -> NDArray[np.float64]:
    """Random points inside an oriented box, returned in the lidar frame."""
    local = rng.uniform(-0.5, 0.5, (n, 3)) * size[[1, 0, 2]]  # x=length, y=width
    global_pts: NDArray[np.float64] = local @ Quaternion(*_yaw_quat(yaw)).rotation_matrix.T + center
    out: NDArray[np.float64] = global_pts @ T_global_to_lidar[:3, :3].T + T_global_to_lidar[:3, 3]
    return out


def build_synthetic_scene(n_samples: int = 8, seed: int = 0) -> tuple[SceneMeta, list[FrameBundle]]:
    rng = np.random.default_rng(seed)
    scene = SceneMeta(
        token="synthetic-scene-0001",  # nosec B106: fixture ID, not a credential
        name="synthetic-0001",
        description="Synthetic fixture: urban drive with injected faults",
        weather="clear",
        time_of_day="day",
    )

    frames: list[FrameBundle] = []
    T_lidar_to_ego = _transform(np.array([0.0, 0.0, 1.8]))  # roof lidar

    for i in range(n_samples):
        t_us = int(i * DT_S * 1e6)
        ego_x = i * EGO_SPEED_MPS * DT_S
        T_ego_lidar_global = _transform(np.array([ego_x, 0.0, 0.0]))
        T_ego_cam_global = _transform(np.array([ego_x + 0.01, 0.0, 0.0]))  # tiny skew

        car_x = 20.0 + i * CAR_SPEED_MPS * DT_S
        if i == 3:  # injected teleport -> acceleration spike
            car_x += 30.0
        size = np.array([1.8, 4.2, 1.6])
        if i == 6:  # injected volume drift
            size = size * 1.6
        car = AnnBox(
            token=f"ann-car-{i}",
            instance_token="inst-car-1",  # nosec B106: fixture ID
            category="vehicle.car",
            center=np.array([car_x, 0.0, 0.8]),
            size=size,
            orientation=_yaw_quat(0.0),
            radar_returns=4,
        )

        boxes = [car]
        if i == 5:  # injected ghost label: no lidar support, 12 m away
            boxes.append(
                AnnBox(
                    token="ann-ghost-5",  # nosec B106: fixture ID
                    instance_token="inst-ghost-1",
                    category="vehicle.car",
                    center=np.array([ego_x + 12.0, -2.0, 0.8]),
                    size=np.array([1.8, 4.2, 1.6]),
                    orientation=_yaw_quat(0.0),
                    radar_returns=0,
                )
            )

        # ground plane annulus + box-clustered returns, all in lidar frame
        ground_r = rng.uniform(5.0, 50.0, 600)
        ground_th = rng.uniform(-np.pi, np.pi, 600)
        ground = np.column_stack(
            [ground_r * np.cos(ground_th), ground_r * np.sin(ground_th), np.full(600, -2.5)]
        )
        T_global_to_lidar = np.linalg.inv(T_ego_lidar_global @ T_lidar_to_ego)
        box_pts = _box_points_in_lidar(rng, car.center, car.size, 0.0, T_global_to_lidar, n=400)
        points = np.vstack([ground, box_pts])

        image = rng.integers(30, 90, (IMG_H, IMG_W, 3), dtype=np.uint8)
        image[180:] = (image[180:] * 0.6 + 40).astype(np.uint8)  # darker road half
        if i == 4:  # injected underexposure
            image = (image * 0.05).astype(np.uint8)

        frames.append(
            FrameBundle(
                sample_token=f"sample-{i:04d}",
                scene_token=scene.token,
                timestamp_us=t_us,
                ego_speed_mps=EGO_SPEED_MPS,
                image=image,
                lidar_points=points,
                radar_total_returns=18,
                boxes=boxes,
                T_lidar_to_ego=T_lidar_to_ego,
                T_ego_lidar_to_global=T_ego_lidar_global,
                T_ego_cam_to_global=T_ego_cam_global,
                T_cam_to_ego=T_CAM_TO_EGO,
                K=K_MATRIX,
            )
        )
    return scene, frames


def dump_fixture_dataset(scene: SceneMeta, frames: list[FrameBundle], root: str) -> None:
    """Write the fixture layout that `ingestion.load_fixture_frames` reads."""
    import json
    import os

    import cv2

    os.makedirs(f"{root}/images", exist_ok=True)
    os.makedirs(f"{root}/points", exist_ok=True)

    samples = []
    for f in frames:
        cv2.imwrite(f"{root}/images/{f.sample_token}.jpg", cv2.cvtColor(f.image, cv2.COLOR_RGB2BGR))
        np.save(f"{root}/points/{f.sample_token}.npy", f.lidar_points)
        samples.append(
            {
                "sample_token": f.sample_token,
                "scene_token": f.scene_token,
                "timestamp_us": f.timestamp_us,
                "ego_speed_mps": f.ego_speed_mps,
                "image": f"images/{f.sample_token}.jpg",
                "points": f"points/{f.sample_token}.npy",
                "radar_total_returns": f.radar_total_returns,
                "T_lidar_to_ego": f.T_lidar_to_ego.tolist(),
                "T_ego_lidar_to_global": f.T_ego_lidar_to_global.tolist(),
                "T_ego_cam_to_global": f.T_ego_cam_to_global.tolist(),
                "T_cam_to_ego": f.T_cam_to_ego.tolist(),
                "K": f.K.tolist(),
                "boxes": [
                    {
                        "token": b.token,
                        "instance_token": b.instance_token,
                        "category": b.category,
                        "center": b.center.tolist(),
                        "size": b.size.tolist(),
                        "orientation": b.orientation.tolist(),
                        "radar_returns": b.radar_returns,
                    }
                    for b in f.boxes
                ],
            }
        )

    meta = {
        "scenes": [
            {
                "token": scene.token,
                "name": scene.name,
                "description": scene.description,
                "weather": scene.weather,
                "time_of_day": scene.time_of_day,
            }
        ],
        "samples": samples,
    }
    with open(f"{root}/fixture.json", "w") as fh:
        json.dump(meta, fh, indent=2)
