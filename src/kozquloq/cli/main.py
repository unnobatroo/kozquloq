"""kozquloq CLI (spec §6): demo, audit, report, diagnose, chat."""

from __future__ import annotations

import contextlib
import os
import webbrowser
from typing import TYPE_CHECKING

import typer
from rich.markdown import Markdown

from kozquloq.agent.diagnostics import DiagnosticAgent
from kozquloq.cli.console import (
    console,
    health_table,
    slices_table,
    worst_table,
)
from kozquloq.storage import views
from kozquloq.storage.duckdb_store import Store

if TYPE_CHECKING:
    from kozquloq.types import FrameBundle, SceneMeta

app = typer.Typer(help="Kozquloq: AV sensor data quality & diagnostics pipeline.")


def _audit_scenes(
    store: Store,
    scenes: list[tuple[SceneMeta, list[FrameBundle]]],
    source: str,
) -> None:
    from rich.progress import Progress

    from kozquloq.pipeline import run_audit

    total = sum(len(f) for _, f in scenes)
    console.print(f"[bold]Auditing {total} keyframes[/] from {source}")
    with Progress(console=console) as progress:
        task = progress.add_task("auditing", total=total)
        run_audit(scenes, store, on_progress=lambda _b: progress.advance(task), clear=True)


@app.command()
def demo(
    browser: bool = typer.Option(True, "--browser/--no-browser"),
) -> None:
    """Zero-setup demo: synthetic scene -> audit -> terminal summary + HTML report."""
    from kozquloq.synthetic import build_synthetic_scene
    from kozquloq.visualization.report_generator import render_report

    store = Store(":memory:")
    scene, frames = build_synthetic_scene(n_samples=8)
    _audit_scenes(store, [(scene, frames)], "synthetic fixture scene")

    console.print(health_table(views.health_summary(store)))
    console.print(slices_table(views.slice_failure_rates(store)))
    console.print(worst_table(views.worst_samples(store)))

    out = render_report(store, "audit_report.html")
    console.print(f"[bold green]Report written to {out.resolve()}[/]")
    if browser:
        with contextlib.suppress(Exception):
            webbrowser.open(out.resolve().as_uri())


@app.command()
def audit(
    dataroot: str | None = typer.Option(None, help="nuScenes or fixture dataset root"),
    version: str = typer.Option("v1.0-mini"),
    db: str = typer.Option("data/kozquloq.duckdb"),
) -> None:
    """Run the end-to-end audit and populate DuckDB."""
    from kozquloq.ingestion import load_frames
    from kozquloq.synthetic import build_synthetic_scene

    if dataroot and os.path.isdir(dataroot):
        scenes = list(load_frames(dataroot, version))
        source = f"dataset at {dataroot}"
    else:
        if dataroot:
            console.print(f"[yellow]dataroot {dataroot} not found — using synthetic fixtures[/]")
        scenes = [build_synthetic_scene(n_samples=8)]
        source = "synthetic fixture scene"

    store = Store(db)
    _audit_scenes(store, scenes, source)
    console.print(health_table(views.health_summary(store)))
    console.print(f"[bold green]Audit written to {db}[/]")


@app.command()
def report(
    db: str = typer.Option("data/kozquloq.duckdb"),
    html: bool = typer.Option(True, "--html/--no-html"),
    serve: bool = typer.Option(False, "--serve/--no-serve"),
    out: str = typer.Option("audit_report.html"),
    json_out: str | None = typer.Option(None, "--json-out", help="Export dashboard JSON"),
) -> None:
    """Terminal summary + optional HTML report from an audited database."""
    from kozquloq.visualization.report_generator import export_report_json, render_report

    store = Store(db)
    console.print(health_table(views.health_summary(store)))
    console.print(slices_table(views.slice_failure_rates(store)))
    if html:
        path = render_report(store, out)
        console.print(f"[bold green]Report written to {path.resolve()}[/]")
        if serve:
            webbrowser.open(path.resolve().as_uri())
    if json_out:
        jpath = export_report_json(store, json_out)
        console.print(f"[bold green]Dashboard JSON written to {jpath.resolve()}[/]")


@app.command()
def diagnose(
    query: str,
    provider: str = typer.Option("mock"),
    db: str = typer.Option("data/kozquloq.duckdb"),
) -> None:
    """Run the diagnostic agent against the audit database."""
    store = Store(db)
    result = DiagnosticAgent(store, provider=provider).run(query)
    console.print(Markdown(result.report))
    console.print(f"[dim]tools used: {', '.join(result.tool_calls)}[/]")


@app.command()
def chat(
    db: str = typer.Option("data/kozquloq.duckdb"),
    report: str = typer.Option("audit_report.html"),
) -> None:
    """Launch the interactive diagnostic REPL."""
    from kozquloq.cli.repl import run_repl

    run_repl(db, report)


if __name__ == "__main__":
    app()
