import numpy as np

from kozquloq.auditors.geometry import (
    audit_frame_geometry,
    box_corners_global,
    points_in_box,
    project_corners_to_camera,
    project_lidar_to_camera,
    quat_to_rot,
)
from kozquloq.types import AnnBox, FrameBundle


def test_quat_to_rot_identity() -> None:
    assert np.allclose(quat_to_rot(np.array([1.0, 0, 0, 0])), np.eye(3))


def test_quat_to_rot_90deg_yaw() -> None:
    R = quat_to_rot(np.array([np.cos(np.pi / 4), 0, 0, np.sin(np.pi / 4)]))
    assert np.allclose(R @ np.array([1.0, 0, 0]), [0, 1, 0], atol=1e-9)


def test_points_in_box() -> None:
    box = AnnBox(
        token="b",
        instance_token="i",
        category="vehicle.car",
        center=np.array([10.0, 0.0, 0.8]),
        size=np.array([2.0, 4.0, 2.0]),
        orientation=np.array([1.0, 0, 0, 0]),
    )

    # nuScenes local frame: x = length (bound 4/2), y = width (bound 2/2)
    inside = np.array([[10.0, 0.0, 0.8], [11.9, 0.9, 1.7]])
    outside = np.array([[12.1, 0.0, 0.8], [10.0, 1.1, 0.8]])
    assert points_in_box(inside, box).all()
    assert not points_in_box(outside, box).any()


def test_lidar_to_camera_projection(bundle: FrameBundle) -> None:
    uv, depth, in_image, pts_global = project_lidar_to_camera(bundle)
    n = len(bundle.lidar_points)
    assert uv.shape == (n, 2)
    assert depth.shape == (n,)
    assert pts_global.shape == (n, 3)
    # box-clustered points 10 m ahead must land inside the 640x360 frame
    assert in_image.sum() > 100


def test_box_corners_project_into_frame(bundle: FrameBundle) -> None:
    uv, depth = project_corners_to_camera(bundle, box_corners_global(bundle.boxes[0]))
    assert uv.shape == (8, 2)
    assert (depth > 0).all()
    assert (uv[:, 0] > 0).all() and (uv[:, 0] < 640).all()


def test_ghost_detection(bundle: FrameBundle) -> None:
    results = audit_frame_geometry(bundle)
    by_token = {r.annotation_token: r for r in results}
    assert by_token["ann-1"].lidar_point_count > 300
    assert not by_token["ann-1"].is_ghost_label
    assert by_token["ann-ghost"].lidar_point_count == 0
    assert by_token["ann-ghost"].is_ghost_label
    assert by_token["ann-1"].is_visible_on_camera
    assert 9 < by_token["ann-1"].distance_to_ego_m < 11
