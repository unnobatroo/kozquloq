from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest

from kozquloq.storage.duckdb_store import Store
from kozquloq.synthetic import K_MATRIX, T_CAM_TO_EGO, build_synthetic_scene
from kozquloq.types import AnnBox, FrameBundle, SceneMeta

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture()
def bundle() -> FrameBundle:
    """Single frame: identity ego pose, known intrinsics, 1000-point cloud,
    one box 10 m ahead with points inside, one empty box (ghost)."""
    rng = np.random.default_rng(7)

    box = AnnBox(
        token="ann-1",
        instance_token="inst-1",
        category="vehicle.car",
        center=np.array([10.0, 0.0, 0.8]),
        size=np.array([1.8, 4.2, 1.6]),
        orientation=np.array([1.0, 0.0, 0.0, 0.0]),
        radar_returns=3,
    )
    ghost = AnnBox(
        token="ann-ghost",
        instance_token="inst-ghost",
        category="vehicle.car",
        center=np.array([15.0, 2.0, 0.8]),
        size=np.array([1.8, 4.2, 1.6]),
        orientation=np.array([1.0, 0.0, 0.0, 0.0]),
        radar_returns=0,
    )

    # 600 ground + 400 inside the box, expressed in the lidar frame
    T_lidar_to_ego = np.eye(4)
    T_lidar_to_ego[:3, 3] = [0.0, 0.0, 1.8]
    T_ego_lidar_global = np.eye(4)
    T_global_to_lidar = np.linalg.inv(T_ego_lidar_global @ T_lidar_to_ego)

    ground = np.column_stack(
        [
            rng.uniform(5.0, 50.0, 600),
            rng.uniform(-20.0, 20.0, 600),
            np.full(600, -2.5),
        ]
    )
    # nuScenes local frame: x = length, y = width
    box_pts_global = rng.uniform(-0.5, 0.5, (400, 3)) * box.size[[1, 0, 2]] + box.center
    box_pts = box_pts_global @ T_global_to_lidar[:3, :3].T + T_global_to_lidar[:3, 3]
    points = np.vstack([ground, box_pts])

    image = rng.integers(60, 120, (360, 640, 3), dtype=np.uint8)
    return FrameBundle(
        sample_token="sample-0000",
        scene_token="scene-0001",
        timestamp_us=0,
        ego_speed_mps=0.0,
        image=image,
        lidar_points=points,
        radar_total_returns=10,
        boxes=[box, ghost],
        T_lidar_to_ego=T_lidar_to_ego,
        T_ego_lidar_to_global=T_ego_lidar_global,
        T_ego_cam_to_global=np.eye(4),
        T_cam_to_ego=T_CAM_TO_EGO,
        K=K_MATRIX,
    )


@pytest.fixture()
def synthetic_frames() -> tuple[SceneMeta, list[FrameBundle]]:
    return build_synthetic_scene(n_samples=8, seed=0)


@pytest.fixture()
def store() -> Iterator[Store]:
    s = Store(":memory:")
    yield s
    s.close()


@pytest.fixture()
def audited_store(store: Store, synthetic_frames: tuple[SceneMeta, list[FrameBundle]]) -> Store:
    from kozquloq.pipeline import run_audit

    run_audit([synthetic_frames], store)
    return store
