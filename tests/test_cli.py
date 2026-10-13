from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from typer.testing import CliRunner

if TYPE_CHECKING:
    import pytest

from kozquloq.cli.main import app
from kozquloq.synthetic import build_synthetic_scene, dump_fixture_dataset

runner = CliRunner()


def test_demo_no_browser(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["demo", "--no-browser"])
    assert result.exit_code == 0, result.output
    assert "Dataset Health" in result.output
    assert (tmp_path / "audit_report.html").exists()


def test_audit_report_diagnose_roundtrip(tmp_path: Path) -> None:
    scene, frames = build_synthetic_scene(n_samples=4)
    fx = str(tmp_path / "fx")
    dump_fixture_dataset(scene, frames, fx)
    db = str(tmp_path / "a.duckdb")

    r = runner.invoke(app, ["audit", "--dataroot", fx, "--db", db])
    assert r.exit_code == 0, r.output
    assert Path(db).exists()

    r = runner.invoke(app, ["report", "--db", db, "--no-html"])
    assert r.exit_code == 0 and "Slice Failure Rates" in r.output

    r = runner.invoke(app, ["report", "--db", db, "--out", str(tmp_path / "r.html")])
    assert r.exit_code == 0
    assert (tmp_path / "r.html").read_text().startswith("<!DOCTYPE")

    r = runner.invoke(app, ["diagnose", "what is wrong?", "--db", db])
    assert r.exit_code == 0 and "Diagnostic report" in r.output

    r = runner.invoke(app, ["diagnose", "x", "--provider", "bogus", "--db", db])
    assert r.exit_code != 0


def test_chat_repl(tmp_path: Path) -> None:
    from kozquloq.storage.duckdb_store import Store

    db = str(tmp_path / "chat.duckdb")
    Store(db).close()
    r = runner.invoke(
        app,
        ["chat", "--db", db, "--report", str(tmp_path / "r.html")],
        input="/summary\n/slices\n/worst\n/report\n/help\n/bogus\n/exit\n",
    )
    assert r.exit_code == 0, r.output
    assert "Dataset Health" in r.output
