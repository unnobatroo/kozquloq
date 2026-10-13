"""Standalone dark-UI HTML report (spec §5.2): health card, slice matrix,
interactive gallery of the top-10 anomalies, embedded diagnostic summary."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import Environment, select_autoescape

from kozquloq.storage import views

if TYPE_CHECKING:
    from kozquloq.auditors.geometry import BoxAuditResult
    from kozquloq.storage.duckdb_store import Store
    from kozquloq.types import FrameBundle


@dataclass
class GalleryItem:
    sample_token: str
    caption: str
    images: dict[str, str]  # variant -> base64 jpeg


def _b64(jpeg: bytes) -> str:
    return base64.b64encode(jpeg).decode("ascii")


def collect_gallery(store: Store, limit: int = 10) -> list[GalleryItem]:
    rows = store.query(
        """
        SELECT a.annotation_token, a.sample_token, a.category, a.severity_score,
               a.is_ghost_label, a.is_kinematic_outlier, a.is_scale_unstable,
               a.lidar_point_count
        FROM annotation_audits a
        ORDER BY a.severity_score DESC, a.sample_token
        LIMIT ?
        """,
        [limit * 4],  # oversample: several top annotations may share one frame
    )
    items = []
    seen: set[str] = set()
    for r in rows:
        if r["sample_token"] in seen or len(items) >= limit:
            continue
        seen.add(r["sample_token"])
        imgs = views.sample_images(store, r["sample_token"])
        if not imgs:
            continue
        flags = [
            n
            for n, on in (
                ("GHOST", r["is_ghost_label"]),
                ("KINEMATIC", r["is_kinematic_outlier"]),
                ("SCALE", r["is_scale_unstable"]),
            )
            if on
        ] or ["CLEAN"]
        items.append(
            GalleryItem(
                sample_token=r["sample_token"],
                caption=(
                    f"{r['category']} | {' / '.join(flags)} | "
                    f"sev {r['severity_score']:.2f} | pts {r['lidar_point_count']}"
                ),
                images={k: _b64(v) for k, v in imgs.items()},
            )
        )
    return items


def render_report(
    store: Store,
    out_path: str | Path,
    diagnostics_md: str = "",
) -> Path:
    env = Environment(autoescape=select_autoescape())
    template = env.from_string(
        resources.files("kozquloq.visualization.templates")
        .joinpath("report.html.jinja")
        .read_text()
    )
    health = views.health_summary(store)
    html = template.render(
        health=health,
        slices=views.slice_failure_rates(store),
        gallery=collect_gallery(store),
        diagnostics=diagnostics_md,
    )
    out = Path(out_path)
    out.write_text(html)
    return out


def build_frame_overlays(
    bundle: FrameBundle, box_results: list[BoxAuditResult]
) -> dict[str, bytes]:
    """Render the three overlay variants of one frame for storage in DuckDB."""
    from kozquloq.auditors.geometry import (
        box_corners_global,
        project_corners_to_camera,
        project_lidar_to_camera,
    )
    from kozquloq.visualization.overlay import (
        draw_3d_boxes_on_image,
        draw_lidar_points_on_image,
        encode_jpeg,
    )

    uv, depth, in_image, _ = project_lidar_to_camera(bundle)
    corners = [project_corners_to_camera(bundle, box_corners_global(b))[0] for b in bundle.boxes]

    with_points = draw_lidar_points_on_image(bundle.image, uv[in_image], depth[in_image])
    full = draw_3d_boxes_on_image(with_points, corners, box_results)
    boxes_only = draw_3d_boxes_on_image(bundle.image, corners, box_results)
    flagged = draw_3d_boxes_on_image(bundle.image, corners, box_results, only_flagged=True)
    return {
        "full": encode_jpeg(full),
        "boxes": encode_jpeg(boxes_only),
        "flagged": encode_jpeg(flagged),
    }
