from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from kozquloq.storage.duckdb_store import Store


def _seed(store: Store) -> None:
    store.insert_many(
        "samples",
        [
            {
                "sample_token": "sa1",
                "scene_name": "scene-1",
                "weather": "rain",
                "time_of_day": "night",
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
        "audits",
        [
            {
                "annotation_token": "a1",
                "sample_token": "sa1",
                "instance_token": "i1",
                "category": "vehicle.car",
                "distance_to_ego_m": 10.0,
                "lidar_points": 50,
                "radar_return_count": 2,
                "is_ghost": True,
                "is_visible_on_camera": True,
                "velocity_mps": 1.0,
                "acceleration_mps2": None,
                "volume_variance_ratio": None,
                "is_kinematic_outlier": False,
                "is_scale_unstable": False,
                "severity": 0.55,
            },
            {
                "annotation_token": "a2",
                "sample_token": "sa1",
                "instance_token": "i2",
                "category": "vehicle.car",
                "distance_to_ego_m": 30.0,
                "lidar_points": 10,
                "radar_return_count": 0,
                "is_ghost": False,
                "is_visible_on_camera": False,
                "velocity_mps": None,
                "acceleration_mps2": None,
                "volume_variance_ratio": None,
                "is_kinematic_outlier": False,
                "is_scale_unstable": False,
                "severity": 0.0,
            },
        ],
    )


def test_schema_and_inserts(store: Store) -> None:
    _seed(store)
    assert store.query("SELECT COUNT(*) AS n FROM samples")[0]["n"] == 1
    assert store.query("SELECT COUNT(*) AS n FROM audits")[0]["n"] == 2


def test_slice_failure_view(store: Store) -> None:
    _seed(store)
    rows = store.get_slice_metrics()
    assert len(rows) == 1
    r = rows[0]
    assert r["weather"] == "rain"
    assert r["time_of_day"] == "night"
    assert r["total_annotations"] == 2
    assert r["ghost_labels_count"] == 1
    assert r["failure_rate_pct"] == 50.0


def test_severe_outliers_view(store: Store) -> None:
    _seed(store)
    rows = store.query("SELECT annotation_token, scene_name FROM view_severe_outliers")
    assert [r["annotation_token"] for r in rows] == ["a1"]
    assert rows[0]["scene_name"] == "scene-1"


def test_get_invalid_tokens(store: Store) -> None:
    _seed(store)
    rows = store.get_invalid_tokens()
    assert [r["annotation_token"] for r in rows] == ["a1"]
    assert "ghost" in rows[0]["reason"]
    assert store.get_invalid_tokens(min_severity=0.9) == []


def test_health_summary(store: Store) -> None:
    _seed(store)
    h = store.get_summary()
    assert h["frames"] == 1
    assert h["flagged"] == 1
    assert h["grade"] == "F"


def test_query_numpy(store: Store) -> None:
    _seed(store)
    table = store.query_numpy("SELECT annotation_token, lidar_points FROM audits ORDER BY 1")
    assert len(table["annotation_token"]) == 2
    assert table["lidar_points"].tolist() == [50, 10]


def test_export_parquet(store: Store, tmp_path: Path) -> None:
    _seed(store)
    out = tmp_path / "audits.parquet"
    store.export_parquet(str(out))
    assert out.exists()
    rows = store.query("SELECT COUNT(*) AS n FROM read_parquet(?)", [str(out)])
    assert rows[0]["n"] == 2


def test_audit_pipeline_populates_db(audited_store: Store) -> None:
    h = audited_store.get_summary()
    assert h["frames"] == 8
    assert h["annotations"] == 9
    assert h["ghosts"] == 1
    assert h["kinematic_outliers"] >= 1
    assert h["scale_unstable"] >= 1
    assert h["underexposed_frames"] == 1
