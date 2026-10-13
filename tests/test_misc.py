from __future__ import annotations

from typing import TYPE_CHECKING

import torch

from kozquloq.agent.providers import get_provider
from kozquloq.auditors import audit_frame
from kozquloq.config import Settings
from kozquloq.pytorch.transforms import Normalize, compose

if TYPE_CHECKING:
    from pathlib import Path

    from kozquloq.storage.duckdb_store import Store
    from kozquloq.types import FrameBundle


def test_audit_frame_convenience(bundle: FrameBundle) -> None:
    health, boxes = audit_frame(bundle)
    assert health.lidar_total_points == len(bundle.lidar_points)
    assert len(boxes) == 2
    assert any(b.is_ghost_label for b in boxes)


def test_settings_defaults() -> None:
    s = Settings()
    assert s.version == "v1.0-mini"


def test_transforms() -> None:
    rows = [torch.ones(4), torch.zeros(4)]
    norm = Normalize.from_rows(rows)
    out = compose(norm)(torch.ones(4))
    assert out.shape == (4,)
    assert torch.isfinite(out).all()


def test_get_provider_errors() -> None:
    import pytest

    assert isinstance(get_provider("mock"), object)
    with pytest.raises(ValueError, match="unknown provider"):
        get_provider("bogus")


def test_store_clear_and_export(store: Store, tmp_path: Path) -> None:
    import pytest

    from kozquloq.storage import views

    store.insert_many(
        "scenes",
        [
            {
                "scene_token": "s",
                "name": "n",
                "description": "",
                "weather": "clear",
                "time_of_day": "day",
                "nbr_samples": 0,
            }
        ],
    )
    assert store.query_slice() == []
    assert store.get_summary()["frames"] == 0
    store.export_parquet(str(tmp_path / "pq"))
    assert (tmp_path / "pq" / "scenes.parquet").exists()
    store.clear()
    assert views.slice_failure_rates(store) == []
    import duckdb

    with pytest.raises(duckdb.Error):
        store.query("SELECT nope FROM nowhere")
