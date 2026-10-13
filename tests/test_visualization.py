from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from kozquloq.auditors.geometry import (
    audit_frame_geometry,
    box_corners_global,
    project_corners_to_camera,
    project_lidar_to_camera,
)
from kozquloq.visualization.overlay import (
    draw_3d_boxes_on_image,
    draw_lidar_points_on_image,
    encode_jpeg,
)
from kozquloq.visualization.report_generator import render_report

if TYPE_CHECKING:
    from pathlib import Path

    from kozquloq.storage.duckdb_store import Store
    from kozquloq.types import FrameBundle


def test_draw_lidar_points(bundle: FrameBundle) -> None:
    uv, depth, in_image, _ = project_lidar_to_camera(bundle)
    out = draw_lidar_points_on_image(bundle.image, uv[in_image], depth[in_image])
    assert out.shape == bundle.image.shape
    assert out.dtype == np.uint8
    assert not np.array_equal(out, bundle.image)  # points actually drawn


def test_draw_boxes_colors(bundle: FrameBundle) -> None:
    results = audit_frame_geometry(bundle)
    for r in results:
        r.finalize_severity()
    corners = [project_corners_to_camera(bundle, box_corners_global(b))[0] for b in bundle.boxes]
    out = draw_3d_boxes_on_image(bundle.image, corners, results)
    assert out.shape == bundle.image.shape and out.dtype == np.uint8
    assert not np.array_equal(out, bundle.image)

    flagged_only = draw_3d_boxes_on_image(bundle.image, corners, results, only_flagged=True)
    assert flagged_only.shape == bundle.image.shape


def test_encode_jpeg(bundle: FrameBundle) -> None:
    assert encode_jpeg(bundle.image)[:2] == b"\xff\xd8"


def test_render_report(audited_store: Store, tmp_path: Path) -> None:
    out = render_report(audited_store, tmp_path / "r.html", diagnostics_md="test findings")
    html = out.read_text()
    assert "<html" in html
    assert "data:image/jpeg;base64," in html
    assert "Slice Degradation Matrix" in html
    assert "test findings" in html
    assert "vehicle.car" in html
