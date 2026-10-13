from __future__ import annotations

from typing import TYPE_CHECKING

from kozquloq.auditors import audit_frame
from kozquloq.config import Settings

if TYPE_CHECKING:
    from kozquloq.storage.duckdb_store import Store
    from kozquloq.types import FrameBundle


def test_audit_frame_convenience(bundle: FrameBundle) -> None:
    health, boxes = audit_frame(bundle)
    assert health.lidar_total_points == len(bundle.lidar_points)
    assert len(boxes) == 2
    assert any(b.is_ghost for b in boxes)


def test_settings_defaults() -> None:
    s = Settings()
    assert s.version == "v1.0-mini"


def test_store_clear_and_export(store: Store) -> None:
    import pytest

    store.insert_many(
        "samples",
        [
            {
                "sample_token": "sa1",
                "scene_name": "n",
                "weather": "clear",
                "time_of_day": "day",
                "timestamp": 1,
                "ego_speed_mps": 0.0,
                "camera_underexposed_count": 0,
                "lidar_total_points": 0,
                "radar_total_returns": 0,
                "has_geometric_drift": False,
            }
        ],
    )
    assert store.get_slice_metrics() == []
    assert store.get_summary()["frames"] == 1
    store.clear()
    assert store.get_slice_metrics() == []
    import duckdb

    with pytest.raises(duckdb.Error):
        store.query("SELECT nope FROM nowhere")
