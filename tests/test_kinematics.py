from collections.abc import Sequence

import numpy as np

from kozquloq.auditors.geometry import BoxAuditResult
from kozquloq.auditors.kinematics import KinematicTracker


def _result(
    instance: str, pos: Sequence[float], size: Sequence[float], category: str = "vehicle.car"
) -> BoxAuditResult:
    return BoxAuditResult(
        annotation_token=f"ann-{instance}",
        instance_token=instance,
        category=category,
        distance_to_ego_m=float(np.linalg.norm(pos)),
        lidar_point_count=100,
        radar_return_count=2,
        is_ghost=False,
        is_visible_on_camera=True,
        center_global=np.asarray(pos, dtype=np.float64),
        volume_m3=float(np.prod(size)),
    )


def test_acceleration_violation_vehicle() -> None:
    t = KinematicTracker()
    size = [1.8, 4.2, 1.6]
    # v jumps 0 -> 8 -> 16 m/s in 0.5 s steps => a = 16 m/s^2 > 12
    r0, r1, r2 = (_result("i1", [x, 0, 0.8], size) for x in (0.0, 4.0, 12.0))
    t.update(r0, 0.0)
    t.update(r1, 0.5)
    t.update(r2, 1.0)
    assert r2.acceleration_mps2 == 16.0
    assert r2.is_kinematic_outlier


def test_steady_velocity_no_violation() -> None:
    t = KinematicTracker()
    size = [1.8, 4.2, 1.6]
    rs = [_result("i1", [x, 0, 0.8], size) for x in (0.0, 3.0, 6.0)]
    for r, ts in zip(rs, (0.0, 0.5, 1.0), strict=True):
        t.update(r, ts)
    assert rs[2].acceleration_mps2 == 0.0
    assert not rs[2].is_kinematic_outlier
    assert rs[2].velocity_mps == 6.0


def test_pedestrian_lower_threshold() -> None:
    t = KinematicTracker()
    size = [0.5, 0.5, 1.7]
    rs = [
        _result("p1", [x, 0, 0.8], size, "human.pedestrian.adult")
        for x in (0.0, 2.0, 6.0)  # v: 4 -> 8, a = 8 > 8? boundary
    ]
    for r, ts in zip(rs, (0.0, 0.5, 1.0), strict=True):
        t.update(r, ts)
    assert not rs[2].is_kinematic_outlier  # exactly at threshold

    t2 = KinematicTracker()
    rs = [
        _result("p2", [x, 0, 0.8], size, "human.pedestrian.adult")
        for x in (0.0, 2.0, 6.5)  # v: 4 -> 9 m/s, a = 10 > 8
    ]
    for r, ts in zip(rs, (0.0, 0.5, 1.0), strict=True):
        t2.update(r, ts)
    assert rs[2].is_kinematic_outlier


def test_volume_variance_detection() -> None:
    t = KinematicTracker()
    r0 = _result("i1", [0, 0, 0.8], [1.8, 4.2, 1.6])
    r1 = _result("i1", [1, 0, 0.8], [2.4, 4.2, 1.6])  # +33% volume
    t.update(r0, 0.0)
    t.update(r1, 0.5)
    assert r1.volume_variance_ratio is not None
    assert r1.volume_variance_ratio > 0.15
    assert r1.is_scale_unstable


def test_nonrigid_scale_not_flagged() -> None:
    t = KinematicTracker()
    r0 = _result("i1", [0, 0, 0.8], [0.5, 0.5, 1.7], "human.pedestrian.adult")
    r1 = _result("i1", [0.1, 0, 0.8], [0.7, 0.5, 1.7], "human.pedestrian.adult")
    t.update(r0, 0.0)
    t.update(r1, 0.5)
    assert r1.volume_variance_ratio is not None
    assert r1.volume_variance_ratio > 0.15
    assert not r1.is_scale_unstable
