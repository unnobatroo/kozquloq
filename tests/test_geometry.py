import numpy as np

from kozquloq.auditors.geometry import (
    audit_frame_geometry,
    box_corners_global,
    devkit_box,
    points_in_box,
    project_corners_to_camera,
    project_lidar_to_camera,
)
from kozquloq.types import AnnBox, FrameBundle


def test_devkit_box_adapts_annbox() -> None:
    box = AnnBox(
        token="b",
        instance_token="i",
        category="vehicle.car",
        center=np.array([10.0, 0.0, 0.8]),
        size=np.array([2.0, 4.0, 2.0]),
        orientation=np.array([1.0, 0, 0, 0]),
    )
    b = devkit_box(box)
    assert np.allclose(b.center, [10.0, 0.0, 0.8])
    assert np.allclose(b.wlh, [2.0, 4.0, 2.0])


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
    assert not by_token["ann-1"].is_ghost
    assert by_token["ann-ghost"].lidar_point_count == 0
    assert by_token["ann-ghost"].is_ghost
    assert by_token["ann-1"].is_visible_on_camera
    assert 9 < by_token["ann-1"].distance_to_ego_m < 11


def test_ground_plane_isolation(bundle: FrameBundle) -> None:
    """Road-surface returns (lidar z < -2.0) inside a box must not count."""
    # Lidar sits 1.8 m above the global origin in this fixture, so a global
    # z of -0.8 is lidar z = -2.6: road-surface territory.
    box = AnnBox(
        token="ground-box",
        instance_token="i",
        category="vehicle.car",
        center=np.array([10.0, 0.0, -0.8]),
        size=np.array([2.0, 4.0, 2.0]),
        orientation=np.array([1.0, 0, 0, 0]),
    )
    pts_lidar = np.array([[10.0, 0.0, -2.6]])
    pts_global = pts_lidar + np.array([0.0, 0.0, 1.8])
    assert points_in_box(pts_global, box).all()

    # Same geometry via the full audit: lidar-frame ground points are masked
    # out before occupancy, so the box reads as empty.
    import dataclasses

    b2 = dataclasses.replace(bundle, lidar_points=pts_lidar, boxes=[box])
    (res,) = audit_frame_geometry(b2)
    assert res.lidar_point_count == 0
    assert res.is_ghost  # vehicle category, empty, within range


def test_non_ghostable_category_not_flagged(bundle: FrameBundle) -> None:
    """Empty boxes of non-rigid categories (e.g. animals) are not ghosts."""
    import dataclasses

    animal = AnnBox(
        token="ann-deer",
        instance_token="i-deer",
        category="animal",
        center=np.array([15.0, 2.0, 0.8]),
        size=np.array([1.8, 4.2, 1.6]),
        orientation=np.array([1.0, 0.0, 0.0, 0.0]),
    )
    b2 = dataclasses.replace(bundle, boxes=[animal])
    (res,) = audit_frame_geometry(b2)
    assert res.lidar_point_count == 0
    assert not res.is_ghost


def test_beyond_range_not_ghost(bundle: FrameBundle) -> None:
    """Empty boxes past 35 m are out of lidar range, not ghosts."""
    import dataclasses

    far = AnnBox(
        token="ann-far",
        instance_token="i-far",
        category="vehicle.car",
        center=np.array([60.0, 0.0, 0.8]),
        size=np.array([1.8, 4.2, 1.6]),
        orientation=np.array([1.0, 0.0, 0.0, 0.0]),
    )
    b2 = dataclasses.replace(bundle, boxes=[far])
    (res,) = audit_frame_geometry(b2)
    assert res.lidar_point_count == 0
    assert not res.is_ghost
