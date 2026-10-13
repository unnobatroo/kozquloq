"""Rich terminal rendering helpers (spec §5.3)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

if TYPE_CHECKING:
    from collections.abc import Iterable

console = Console()

T = TypeVar("T")


def track(items: Iterable[T], description: str) -> Iterable[T]:
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        items = list(items)
        task = progress.add_task(description, total=len(items))
        for item in items:
            yield item
            progress.advance(task)


def health_table(health: dict[str, Any]) -> Table:
    t = Table(title="Dataset Health", header_style="bold cyan")
    t.add_column("Metric")
    t.add_column("Value", justify="right")
    grade_style = {"A": "green", "B": "green", "C": "yellow", "D": "red", "F": "bold red"}.get(
        health["grade"], "white"
    )
    t.add_row("Health grade", f"[{grade_style}]{health['grade']}[/]")
    t.add_row("Audited frames", str(health["frames"]))
    t.add_row("Annotations", str(health["annotations"]))
    t.add_row("Flagged anomalies", f"[red]{health['flagged']}[/] ({health['failure_pct']}%)")
    t.add_row("Ghost labels", str(health["ghosts"]))
    t.add_row("Kinematic outliers", str(health["kinematic_outliers"]))
    t.add_row("Scale unstable", str(health["scale_unstable"]))
    t.add_row("Underexposed frames", str(health["underexposed_frames"]))
    t.add_row("Geometric drift frames", str(health["drift_frames"]))
    return t


def slices_table(rows: list[dict[str, Any]]) -> Table:
    t = Table(title="Slice Failure Rates", header_style="bold cyan")
    for col in ("Weather", "Time", "Category", "N", "Ghosts", "Kin.", "Avg pts", "Fail %"):
        t.add_column(col, justify="right" if col not in ("Weather", "Time", "Category") else "left")
    for r in rows:
        pct = r["failure_rate_pct"]
        style = "red" if pct >= 20 else "yellow" if pct > 0 else "white"
        t.add_row(
            r["weather"],
            r["time_of_day"],
            r["category"],
            str(r["total_annotations"]),
            str(r["ghost_labels_count"]),
            str(r["kinematic_outliers_count"]),
            str(r["avg_lidar_points"]),
            f"[{style}]{pct}[/]",
        )
    return t
