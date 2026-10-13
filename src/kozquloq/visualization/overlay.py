"""Static overlay renderer: audit diagnostics drawn onto camera frames.

Images are RGB uint8. Colors are specified in RGB; OpenCV is only used for
primitives/colormap so no channel swap is needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np

from kozquloq.constants import (
    BOX_EDGES,
    COLOR_CLEAN,
    COLOR_GHOST,
    COLOR_KINEMATIC,
    COLOR_SCALE,
)

if TYPE_CHECKING:
    from pathlib import Path

    from numpy.typing import NDArray

    from kozquloq.auditors.geometry import BoxAuditResult
    from kozquloq.types import FrameBundle


def draw_lidar_points_on_image(
    image: NDArray[np.uint8],
    points_2d: NDArray[np.float64],
    depths: NDArray[np.float64],
    max_depth: float = 80.0,
) -> NDArray[np.uint8]:
    """Render lidar points colored by depth (COLORMAP_TURBO), vectorized."""
    out = image.copy()
    if len(points_2d) == 0:
        return out
    norm = np.clip(depths / max_depth, 0.0, 1.0)
    bgr = cv2.applyColorMap((norm * 255).astype(np.uint8), cv2.COLORMAP_TURBO).reshape(-1, 3)
    rgb = bgr[:, ::-1]
    h, w = out.shape[:2]
    ui = points_2d[:, 0].astype(np.int32)
    vi = points_2d[:, 1].astype(np.int32)
    ok = (ui >= 0) & (ui < w) & (vi >= 0) & (vi < h)
    # ~2px dots: stamp a 3x3 cross via four shifted assignments
    out[np.clip(vi[ok], 0, h - 1), np.clip(ui[ok], 0, w - 1)] = rgb[ok]
    for dv, du in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        ok2 = ok & (vi + dv >= 0) & (vi + dv < h) & (ui + du >= 0) & (ui + du < w)
        out[vi[ok2] + dv, ui[ok2] + du] = rgb[ok2]
    return out


def _box_color(audit: BoxAuditResult) -> tuple[int, int, int]:
    if audit.is_ghost:
        return COLOR_GHOST
    if audit.is_kinematic_outlier:
        return COLOR_KINEMATIC
    if audit.is_scale_unstable:
        return COLOR_SCALE
    return COLOR_CLEAN


def draw_3d_boxes_on_image(
    image: NDArray[np.uint8],
    corners_2d: list[NDArray[np.float64]],
    audit_results: list[BoxAuditResult],
    only_flagged: bool = False,
) -> NDArray[np.uint8]:
    """Draw 3D wireframe boxes with color-coded audit badges."""
    out = image.copy()
    h, w = out.shape[:2]
    for corners, audit in zip(corners_2d, audit_results, strict=False):
        if only_flagged and not audit.flagged:
            continue
        color = _box_color(audit)
        pts = corners.astype(int)
        for a, b in BOX_EDGES:
            pa, pb = pts[a], pts[b]
            if (0 <= pa[0] < w or 0 <= pb[0] < w) and (0 <= pa[1] < h or 0 <= pb[1] < h):
                cv2.line(out, tuple(pa), tuple(pb), color, 2)

        status = (
            "GHOST"
            if audit.is_ghost
            else "KIN"
            if audit.is_kinematic_outlier
            else "SCALE"
            if audit.is_scale_unstable
            else "ok"
        )
        label = (
            f"{audit.category.split('.')[-1]} | pts {audit.lidar_point_count} "
            f"| sev {audit.severity:.2f} | {status}"
        )
        x, y = int(pts[:, 0].min()), int(pts[:, 1].min()) - 8
        x = int(np.clip(x, 0, max(0, w - 220)))
        y = int(np.clip(y, 14, h - 4))
        cv2.putText(out, label, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(out, label, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)
    return out


def render_frame_overlay(
    bundle: FrameBundle, audit_results: list[BoxAuditResult]
) -> NDArray[np.uint8]:
    """Lidar depth points + color-coded box wireframes for one frame."""
    from kozquloq.auditors.geometry import (
        box_corners_global,
        project_corners_to_camera,
        project_lidar_to_camera,
    )

    uv, depth, in_image, _ = project_lidar_to_camera(bundle)
    # Skip boxes with no corner in front of the camera: rear boxes project
    # as mirrored/garbage wireframes.
    corners: list[NDArray[np.float64]] = []
    visible: list[BoxAuditResult] = []
    for b, res in zip(bundle.boxes, audit_results, strict=True):
        c2d, z = project_corners_to_camera(bundle, box_corners_global(b))
        if (z > 0.1).any():
            corners.append(c2d)
            visible.append(res)

    out = draw_lidar_points_on_image(bundle.image, uv[in_image], depth[in_image])
    return draw_3d_boxes_on_image(out, corners, visible)


def encode_jpeg(image_rgb: NDArray[np.uint8], quality: int = 80) -> bytes:
    ok, buf = cv2.imencode(
        ".jpg",
        cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR),
        [cv2.IMWRITE_JPEG_QUALITY, quality],
    )
    if not ok:
        raise RuntimeError("JPEG encoding failed")
    return buf.tobytes()


def save_annotated_frame(
    bundle: FrameBundle, audit_results: list[BoxAuditResult], output_dir: str | Path
) -> Path:
    """Render the overlay for one frame and write `{sample_token}.jpg`."""
    from pathlib import Path

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{bundle.sample_token}.jpg"
    path.write_bytes(encode_jpeg(render_frame_overlay(bundle, audit_results)))
    return path


def save_annotated_samples(
    frames: list[tuple[FrameBundle, list[BoxAuditResult]]], output_dir: str | Path
) -> list[Path]:
    """Write annotated overlay JPEGs for a list of (frame, results) pairs."""
    return [save_annotated_frame(bundle, results, output_dir) for bundle, results in frames]
