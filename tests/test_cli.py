from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from kozquloq.cli.main import app

if TYPE_CHECKING:
    import pytest
from kozquloq.synthetic import build_synthetic_scene, dump_fixture_dataset

runner = CliRunner()


def test_demo_no_viz(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["demo", "--no-viz"])
    assert result.exit_code == 0, result.output
    assert "Dataset Health" in result.output


def test_demo_writes_overlays(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["demo", "--viz-dir", str(tmp_path / "viz")])
    assert result.exit_code == 0, result.output
    assert list((tmp_path / "viz").glob("*.jpg"))


def test_scan_export_roundtrip(tmp_path: Path) -> None:
    scene, frames = build_synthetic_scene(n_samples=8)
    fx = str(tmp_path / "fx")
    dump_fixture_dataset(scene, frames, fx)
    db = str(tmp_path / "a.duckdb")

    r = runner.invoke(app, ["scan", "--dataroot", fx, "--db", db])
    assert r.exit_code == 0, r.output
    assert Path(db).exists()
    assert "Dataset Health" in r.output
    assert "Slice Failure Rates" in r.output

    out_json = str(tmp_path / "mask.json")
    r = runner.invoke(app, ["export", "--db", db, "--output", out_json])
    assert r.exit_code == 0, r.output
    rows = json.loads(Path(out_json).read_text())
    assert rows and {"annotation_token", "reason"} <= rows[0].keys()

    out_pq = str(tmp_path / "mask.parquet")
    r = runner.invoke(app, ["export", "--db", db, "--output", out_pq])
    assert r.exit_code == 0, r.output
    assert Path(out_pq).exists()


def test_scan_with_viz_dir(tmp_path: Path) -> None:
    scene, frames = build_synthetic_scene(n_samples=4)
    fx = str(tmp_path / "fx")
    dump_fixture_dataset(scene, frames, fx)
    viz_dir = str(tmp_path / "viz")
    db = str(tmp_path / "a.duckdb")

    r = runner.invoke(app, ["scan", "--dataroot", fx, "--db", db, "--viz-dir", viz_dir])
    assert r.exit_code == 0, r.output
    assert list(Path(viz_dir).glob("*.jpg"))


def test_viz_single_frame(tmp_path: Path) -> None:
    scene, frames = build_synthetic_scene(n_samples=2)
    fx = str(tmp_path / "fx")
    dump_fixture_dataset(scene, frames, fx)

    r = runner.invoke(
        app,
        ["viz", "sample-0000", "--dataroot", fx, "--output-dir", str(tmp_path / "viz")],
    )
    assert r.exit_code == 0, r.output
    assert (tmp_path / "viz" / "sample-0000.jpg").exists()


def test_viz_unknown_token(tmp_path: Path) -> None:
    scene, frames = build_synthetic_scene(n_samples=1)
    fx = str(tmp_path / "fx")
    dump_fixture_dataset(scene, frames, fx)
    r = runner.invoke(app, ["viz", "nope", "--dataroot", fx])
    assert r.exit_code != 0
