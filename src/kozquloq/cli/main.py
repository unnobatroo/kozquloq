"""kozquloq CLI: scan, viz, export, demo."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import typer

from kozquloq.cli.console import console, health_table, slices_table
from kozquloq.storage.duckdb_store import Store

if TYPE_CHECKING:
    from kozquloq.types import FrameBundle, SceneMeta

app = typer.Typer(help="Kozquloq: AV annotation linter (ghosts, kinematics, scale).")


def _scan_scenes(
    store: Store,
    scenes: list[tuple[SceneMeta, list[FrameBundle]]],
    source: str,
    viz_dir: str | None,
) -> None:
    from rich.progress import Progress

    from kozquloq.pipeline import run_audit

    total = sum(len(f) for _, f in scenes)
    console.print(f"[bold]Auditing {total} keyframes[/] from {source}")
    with Progress(console=console) as progress:
        task = progress.add_task("auditing", total=total)
        run_audit(
            scenes,
            store,
            viz_dir=viz_dir,
            on_progress=lambda _b: progress.advance(task),
            clear=True,
        )
    console.print(health_table(store.get_summary()))
    console.print(slices_table(store.get_slice_metrics()))


@app.command()
def scan(
    dataroot: str | None = typer.Option(None, help="nuScenes or fixture dataset root"),
    version: str = typer.Option("v1.0-mini"),
    db: str = typer.Option("data/kozquloq.duckdb"),
    viz_dir: str | None = typer.Option(None, "--viz-dir", help="Write flagged-frame overlays here"),
) -> None:
    """Audit the dataset and print a summary of annotation failures."""
    from kozquloq.ingestion import load_frames
    from kozquloq.synthetic import build_synthetic_scene

    if dataroot and os.path.isdir(dataroot):
        scenes = list(load_frames(dataroot, version))
        source = f"dataset at {dataroot}"
    else:
        if dataroot:
            console.print(f"[yellow]dataroot {dataroot} not found, using synthetic fixtures[/]")
        scenes = [build_synthetic_scene(n_samples=8)]
        source = "synthetic fixture scene"

    store = Store(db)
    _scan_scenes(store, scenes, source, viz_dir)
    console.print(f"[bold green]Audit written to {db}[/]")
    if viz_dir:
        console.print(f"[bold green]Annotated overlays written to {viz_dir}[/]")


@app.command()
def viz(
    sample_token: str,
    dataroot: str = typer.Option(..., help="nuScenes or fixture dataset root"),
    version: str = typer.Option("v1.0-mini"),
    output_dir: str = typer.Option("viz_out"),
) -> None:
    """Overlay boxes + lidar on one keyframe and save the JPEG."""
    from kozquloq.auditors import audit_frame
    from kozquloq.ingestion import load_frames
    from kozquloq.visualization.overlay import save_annotated_frame

    for _scene, frames in load_frames(dataroot, version):
        for bundle in frames:
            if bundle.sample_token == sample_token:
                _, boxes = audit_frame(bundle)
                path = save_annotated_frame(bundle, boxes, output_dir)
                console.print(f"[bold green]Wrote {path.resolve()}[/]")
                return
    raise typer.BadParameter(f"sample_token {sample_token!r} not found under {dataroot}")


@app.command()
def export(
    db: str = typer.Option("data/kozquloq.duckdb"),
    output: str = typer.Option("invalid_tokens.json", "--output"),
    min_severity: float = typer.Option(0.5, "--min-severity"),
) -> None:
    """Export the audit mask: annotation_token + reason for flagged labels.

    Output format follows the file extension: .parquet via DuckDB COPY,
    anything else as JSON.
    """
    store = Store(db)
    if output.endswith(".parquet"):
        store.export_parquet(output)
        console.print(f"[bold green]Parquet mask written to {output}[/]")
        return
    rows = store.get_invalid_tokens(min_severity)
    with open(output, "w") as fh:
        json.dump(rows, fh, indent=2)
    console.print(f"[bold green]{len(rows)} invalid tokens written to {output}[/]")


@app.command()
def demo(
    viz: bool = typer.Option(True, "--viz/--no-viz"),
    viz_dir: str = typer.Option("viz_out"),
) -> None:
    """In-memory synthetic scan; writes a few overlay JPEGs by default."""
    from kozquloq.synthetic import build_synthetic_scene

    store = Store(":memory:")
    scene, frames = build_synthetic_scene(n_samples=8)
    _scan_scenes(store, [(scene, frames)], "synthetic fixture scene", viz_dir if viz else None)


if __name__ == "__main__":
    app()
