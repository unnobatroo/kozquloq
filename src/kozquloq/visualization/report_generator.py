"""Standalone dark-UI HTML report (spec §5.2): health card, slice matrix,
interactive gallery of the top-10 anomalies, embedded diagnostic summary.

Also exports the same data as JSON (`export_report_json`) — the contract
consumed by the TypeScript dashboard in web/."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, select_autoescape

from kozquloq.storage import views

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray

    from kozquloq.auditors.geometry import BoxAuditResult
    from kozquloq.storage.duckdb_store import Store
    from kozquloq.types import FrameBundle


@dataclass
class GalleryItem:
    sample_token: str
    caption: str
    plain: str  # one-line human explanation for the web dashboard
    images: dict[str, str]  # variant -> base64 jpeg


# Plain-English copy for each failure kind — shown verbatim in the UI.
_FLAG_COPY: dict[str, tuple[str, str, str]] = {
    "ghost": (
        "Phantom objects",
        "boxes were drawn where the lidar saw nothing at all",
        "The model learns to detect objects that don't exist — that trains hallucinations.",
    ),
    "kinematic": (
        "Teleporting objects",
        "objects moved faster than physics allows between frames",
        "Usually jittery annotations or a broken track ID — it teaches trackers nonsense.",
    ),
    "scale": (
        "Shapeshifting boxes",
        "objects noticeably changed size between frames",
        "Rigid objects don't resize — these labels can't be trusted.",
    ),
    "underexposed": (
        "Too-dark frames",
        "camera frames are too dark to be usable",
        "The model can't learn from frames it can't see.",
    ),
    "drift": (
        "Sensor misalignment",
        "frames where lidar points don't line up with the camera",
        "Fusion features land in the wrong spot — poisoned training signal.",
    ),
}


def _plain_row(r: dict[str, Any]) -> str:
    cat = r["category"].split(".")[-1].replace("_", " ")
    if r["is_ghost_label"]:
        return f"Someone labeled a '{cat}' here, but the lidar saw empty space."
    if r["is_kinematic_outlier"]:
        v = r.get("velocity_mps")
        speed = f" at {v:.1f} m/s" if v else ""
        return f"This '{cat}' teleported{speed} — no real object moves like that."
    if r["is_scale_unstable"]:
        return f"This '{cat}' changed size between frames — the label is unreliable."
    return f"A '{cat}' — looks fine, shown for context."


def _verdict(grade: str, failure_pct: float) -> str:
    if grade in "AB":
        return f"Looks healthy — only {failure_pct}% of annotations are questionable."
    if grade == "C":
        return f"{failure_pct}% of annotations look wrong — worth a cleanup pass before training."
    return f"{failure_pct}% of annotations look wrong — don't train on this yet."


def _b64(jpeg: bytes) -> str:
    return base64.b64encode(jpeg).decode("ascii")


def collect_gallery(store: Store, limit: int = 10) -> list[GalleryItem]:
    rows = store.query(
        """
        SELECT a.annotation_token, a.sample_token, a.category, a.severity_score,
               a.is_ghost_label, a.is_kinematic_outlier, a.is_scale_unstable,
               a.lidar_point_count, a.velocity_mps
        FROM annotation_audits a
        ORDER BY a.severity_score DESC, a.sample_token
        LIMIT ?
        """,
        [limit * 4],  # oversample: several top annotations may share one frame
    )
    items: list[GalleryItem] = []
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
                plain=_plain_row(r),
                images={k: _b64(v) for k, v in imgs.items()},
            )
        )
    return items


def _chart_data(store: Store) -> dict[str, Any]:
    hist = store.query(
        """
        SELECT CAST(FLOOR(severity_score * 10) / 10 AS DOUBLE) AS bucket,
               COUNT(*) AS n
        FROM annotation_audits
        GROUP BY bucket ORDER BY bucket
        """
    )
    categories = store.query(
        """
        SELECT category, COUNT(*) AS total,
               SUM(CASE WHEN is_ghost_label OR is_kinematic_outlier
                         OR is_scale_unstable THEN 1 ELSE 0 END) AS flagged
        FROM annotation_audits
        GROUP BY category ORDER BY flagged DESC LIMIT 12
        """
    )
    scenes = store.query(
        """
        SELECT sc.name, COUNT(*) AS total,
               SUM(CASE WHEN a.is_ghost_label OR a.is_kinematic_outlier
                         OR a.is_scale_unstable THEN 1 ELSE 0 END) AS flagged
        FROM annotation_audits a
        JOIN samples s ON a.sample_token = s.sample_token
        JOIN scenes sc ON s.scene_token = sc.scene_token
        GROUP BY sc.name ORDER BY sc.name
        """
    )
    return {"severity_hist": hist, "categories": categories, "scenes": scenes}


def _findings(health: dict[str, Any]) -> list[dict[str, Any]]:
    """Plain-English finding cards for the dashboard."""
    annotations = health["annotations"] or 1
    out = []
    for key, count in (
        ("ghost", health["ghosts"]),
        ("kinematic", health["kinematic_outliers"]),
        ("scale", health["scale_unstable"]),
        ("underexposed", health["underexposed_frames"]),
        ("drift", health["drift_frames"]),
    ):
        if not count:
            continue
        title, detail, why = _FLAG_COPY[key]
        pct = round(100.0 * count / annotations, 1)
        out.append(
            {
                "kind": key,
                "title": title,
                "count": count,
                "pct": pct,
                "detail": f"{count:,} {detail} ({pct}% of annotations)",
                "why": why,
            }
        )
    return out


def _write_gallery_assets(store: Store, asset_dir: Path, limit: int) -> list[dict[str, Any]]:
    """Export gallery JPEGs to files (downscaled) and return path-based items."""
    import cv2
    import numpy as np

    asset_dir.mkdir(parents=True, exist_ok=True)
    rows = store.query(
        """
        SELECT a.sample_token, a.category, a.severity_score, a.velocity_mps,
               a.is_ghost_label, a.is_kinematic_outlier, a.is_scale_unstable,
               a.lidar_point_count
        FROM annotation_audits a
        ORDER BY a.severity_score DESC, a.sample_token
        LIMIT ?
        """,
        [limit * 4],
    )
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in rows:
        if r["sample_token"] in seen or len(items) >= limit:
            continue
        seen.add(r["sample_token"])
        imgs = views.sample_images(store, r["sample_token"])
        if not imgs:
            continue
        images: dict[str, str] = {}
        for variant, jpeg in imgs.items():
            arr = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
            if arr.shape[1] > 960:
                arr = cv2.resize(arr, (960, int(arr.shape[0] * 960 / arr.shape[1])))
            ok, buf = cv2.imencode(".jpg", arr, [cv2.IMWRITE_JPEG_QUALITY, 72])
            if not ok:
                continue
            name = f"{r['sample_token'][:12]}_{variant}.jpg"
            (asset_dir / name).write_bytes(buf.tobytes())
            images[variant] = f"assets/{name}"
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
            {
                "sample_token": r["sample_token"],
                "caption": (
                    f"{r['category']} | {' / '.join(flags)} | "
                    f"sev {r['severity_score']:.2f} | pts {r['lidar_point_count']}"
                ),
                "plain": _plain_row(r),
                "images": images,
            }
        )
    return items


def report_payload(store: Store, diagnostics_md: str = "") -> dict[str, Any]:
    """Everything the web dashboard needs, in one JSON-serializable dict."""
    health = views.health_summary(store)
    gallery = collect_gallery(store)
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "health": health,
        "verdict": _verdict(health["grade"], health["failure_pct"]),
        "findings": _findings(health),
        "charts": _chart_data(store),
        "slices": views.slice_failure_rates(store),
        "gallery": [
            {
                "sample_token": g.sample_token,
                "caption": g.caption,
                "plain": g.plain,
                "images": g.images,
            }
            for g in gallery
        ],
        "diagnostics": diagnostics_md,
    }


def export_report_json(store: Store, out_path: str | Path, diagnostics_md: str = "") -> Path:
    """Write the dashboard payload + a sibling assets/ dir of downscaled JPEGs."""
    out = Path(out_path)
    payload = report_payload(store, diagnostics_md)
    payload["gallery"] = _write_gallery_assets(store, out.parent / "assets", limit=10)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload))
    return out


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
    # Keep only boxes with at least one corner in front of the camera —
    # rear boxes project as mirrored/garbage wireframes.
    corners: list[NDArray[np.float64]] = []
    visible_results: list[BoxAuditResult] = []
    for b, res in zip(bundle.boxes, box_results, strict=True):
        c2d, z = project_corners_to_camera(bundle, box_corners_global(b))
        if (z > 0.1).any():
            corners.append(c2d)
            visible_results.append(res)

    with_points = draw_lidar_points_on_image(bundle.image, uv[in_image], depth[in_image])
    full = draw_3d_boxes_on_image(with_points, corners, visible_results)
    boxes_only = draw_3d_boxes_on_image(bundle.image, corners, visible_results)
    flagged = draw_3d_boxes_on_image(bundle.image, corners, visible_results, only_flagged=True)
    return {
        "full": encode_jpeg(full),
        "boxes": encode_jpeg(boxes_only),
        "flagged": encode_jpeg(flagged),
    }
