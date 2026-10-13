from pathlib import Path

import torch
from torch.utils.data import DataLoader

from kozquloq.pipeline import run_audit
from kozquloq.pytorch.dataset import QualityAuditDataset
from kozquloq.types import FrameBundle, SceneMeta


def _make_db(tmp_path: Path, synthetic_frames: tuple[SceneMeta, list[FrameBundle]]) -> str:
    from kozquloq.storage.duckdb_store import Store

    db = str(tmp_path / "audit.duckdb")
    with Store(db) as store:
        run_audit([synthetic_frames], store, save_images=False)
    return db


def test_dataset_quality_masking(
    tmp_path: Path, synthetic_frames: tuple[SceneMeta, list[FrameBundle]]
) -> None:
    db = _make_db(tmp_path, synthetic_frames)
    ds = QualityAuditDataset(db)
    assert len(ds) == 9

    item = ds[0]
    assert item["features"].shape == (6,)
    assert item["features"].dtype == torch.float32
    assert item["label"].dtype == torch.long
    assert 0.0 <= float(item["weight"]) <= 1.0

    labels = [int(ds[i]["label"]) for i in range(len(ds))]
    assert 1 in labels  # ghost + kinematic anomalies exist

    severe = [i for i in range(len(ds)) if ds[i]["severity"] >= 0.5]
    assert all(float(ds[i]["weight"]) == 0.0 for i in severe)


def test_dataset_drop_mode(
    tmp_path: Path, synthetic_frames: tuple[SceneMeta, list[FrameBundle]]
) -> None:
    db = _make_db(tmp_path, synthetic_frames)
    full = QualityAuditDataset(db)
    dropped = QualityAuditDataset(db, min_severity_to_keep=0.5, drop=True)
    assert 0 < len(dropped) < len(full)
    assert all(dropped[i]["severity"] < 0.5 for i in range(len(dropped)))


def test_batch_loading(
    tmp_path: Path, synthetic_frames: tuple[SceneMeta, list[FrameBundle]]
) -> None:
    db = _make_db(tmp_path, synthetic_frames)
    ds = QualityAuditDataset(db)
    loader = DataLoader(ds, batch_size=4)
    batch = next(iter(loader))
    assert batch["features"].shape == (4, 6)
    assert batch["label"].shape == (4,)
    assert batch["weight"].shape == (4,)
