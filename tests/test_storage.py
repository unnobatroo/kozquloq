from __future__ import annotations

from typing import TYPE_CHECKING

from kozquloq.storage import views

if TYPE_CHECKING:
    from kozquloq.storage.duckdb_store import Store


def _seed(store: Store) -> None:
    store.insert_many(
        "scenes",
        [
            {
                "scene_token": "s1",
                "name": "scene-1",
                "description": "d",
                "weather": "rain",
                "time_of_day": "night",
                "nbr_samples": 1,
            }
        ],
    )
    store.insert_many(
        "samples",
        [
            {
                "sample_token": "sa1",
                "scene_token": "s1",
                "timestamp": 100,
                "ego_speed_mps": 5.0,
                "camera_underexposed_count": 0,
                "lidar_total_points": 1000,
                "radar_total_returns": 20,
                "has_geometric_drift": False,
            }
        ],
    )
    store.insert_many(
        "annotation_audits",
        [
            {
                "annotation_token": "a1",
                "sample_token": "sa1",
                "instance_token": "i1",
                "category": "vehicle.car",
                "distance_to_ego_m": 10.0,
                "lidar_point_count": 50,
                "radar_return_count": 2,
                "is_ghost_label": True,
                "is_visible_on_camera": True,
                "velocity_mps": 1.0,
                "acceleration_mps2": None,
                "volume_variance_ratio": None,
                "is_kinematic_outlier": False,
                "is_scale_unstable": False,
                "severity_score": 0.55,
            },
            {
                "annotation_token": "a2",
                "sample_token": "sa1",
                "instance_token": "i2",
                "category": "vehicle.car",
                "distance_to_ego_m": 30.0,
                "lidar_point_count": 10,
                "radar_return_count": 0,
                "is_ghost_label": False,
                "is_visible_on_camera": False,
                "velocity_mps": None,
                "acceleration_mps2": None,
                "volume_variance_ratio": None,
                "is_kinematic_outlier": False,
                "is_scale_unstable": False,
                "severity_score": 0.0,
            },
        ],
    )


def test_schema_and_inserts(store: Store) -> None:
    _seed(store)
    assert store.query("SELECT COUNT(*) AS n FROM scenes")[0]["n"] == 1
    assert store.query("SELECT COUNT(*) AS n FROM samples")[0]["n"] == 1
    assert store.query("SELECT COUNT(*) AS n FROM annotation_audits")[0]["n"] == 2


def test_slice_failure_view(store: Store) -> None:
    _seed(store)
    rows = views.slice_failure_rates(store)
    assert len(rows) == 1
    r = rows[0]
    assert r["weather"] == "rain"
    assert r["time_of_day"] == "night"
    assert r["total_annotations"] == 2
    assert r["ghost_labels_count"] == 1
    assert r["failure_rate_pct"] == 50.0


def test_health_summary(store: Store) -> None:
    _seed(store)
    h = views.health_summary(store)
    assert h["frames"] == 1
    assert h["flagged"] == 1
    assert h["grade"] == "F"


def test_audit_pipeline_populates_db(audited_store: Store) -> None:
    h = views.health_summary(audited_store)
    assert h["frames"] == 8
    assert h["annotations"] == 9
    assert h["ghosts"] == 1
    assert h["kinematic_outliers"] >= 1
    assert h["scale_unstable"] >= 1
    assert h["underexposed_frames"] == 1


def test_overlay_images_stored(audited_store: Store) -> None:
    imgs = views.sample_images(audited_store, "sample-0005")
    assert set(imgs) == {"full", "boxes", "flagged"}
    assert all(len(j) > 500 for j in imgs.values())
