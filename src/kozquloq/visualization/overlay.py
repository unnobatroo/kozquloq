"""Draw audit diagnostics onto camera frames (spec §5.1).

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
    from numpy.typing import NDArray

    from kozquloq.auditors.geometry import BoxAuditResult


def draw_lidar_points_on_image(
    image: NDArray[np.uint8],
    points_2d: NDArray[np.float64],
    depths: NDArray[np.float64],
    max_depth: float = 80.0,
) -> NDArray[np.uint8]:
    """Render lidar points as small circles colored by depth (COLORMAP_TURBO)."""
    out = image.copy()
    if len(points_2d) == 0:
        return out
    norm = np.clip(depths / max_depth, 0.0, 1.0)
    colormap = cv2.applyColorMap((norm * 255).astype(np.uint8), cv2.COLORMAP_TURBO)
    bgr = colormap.reshape(-1, 3)  # BGR per OpenCV convention
    h, w = out.shape[:2]
    for (u, v), (b, g, r) in zip(points_2d, bgr, strict=False):
        ui, vi = int(u), int(v)
        if 0 <= ui < w and 0 <= vi < h:
            cv2.circle(out, (ui, vi), 2, (int(r), int(g), int(b)), -1)  # RGB img
    return out


def _box_color(audit: BoxAuditResult) -> tuple[int, int, int]:
    if audit.is_ghost_label:
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

        label = (
            f"{audit.category.split('.')[-1]} | "
            f"Pts:{audit.lidar_point_count} | Sev:{audit.severity_score:.2f}"
        )
        x, y = int(pts[:, 0].min()), int(pts[:, 1].min()) - 8
        x = int(np.clip(x, 0, max(0, w - 220)))
        y = int(np.clip(y, 14, h - 4))
        cv2.putText(out, label, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(out, label, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)
    return out


def encode_jpeg(image_rgb: NDArray[np.uint8], quality: int = 80) -> bytes:
    ok, buf = cv2.imencode(
        ".jpg",
        cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR),
        [cv2.IMWRITE_JPEG_QUALITY, quality],
    )
    if not ok:
        raise RuntimeError("JPEG encoding failed")
    return buf.tobytes()
