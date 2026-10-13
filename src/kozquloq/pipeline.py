"""End-to-end audit pipeline: frames -> auditors -> store rows + overlays.

Auditors and the storage backend are injected (dependency inversion) — the
orchestrator only knows the `BaseAuditor` and `AuditStore` contracts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from kozquloq.auditors import DEFAULT_AUDITORS, BaseAuditor, FrameFindings
from kozquloq.visualization.report_generator import build_frame_overlays

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from kozquloq.storage.base import AuditStore
    from kozquloq.types import FrameBundle, SceneMeta


class AuditPipeline:
    def __init__(
        self,
        store: AuditStore,
        auditors: Sequence[BaseAuditor] | None = None,
        save_images: bool = True,
    ) -> None:
        self.store = store
        self.auditors = list(auditors) if auditors else [c() for c in DEFAULT_AUDITORS]
        self.save_images = save_images

    def run(
        self,
        scenes: Iterable[tuple[SceneMeta, list[FrameBundle]]],
        on_progress: Callable[[FrameBundle], None] | None = None,
        clear: bool = False,
    ) -> None:
        """Audit every scene and persist scene/sample/audit rows (+ JPEGs).

        The whole run is atomic: an interruption rolls back instead of
        leaving a partially-written (and misleadingly clean-looking) audit.
        """
        with self.store.transaction():
            if clear:
                self.store.clear()
            self._run(scenes, on_progress)

    def _run(
        self,
        scenes: Iterable[tuple[SceneMeta, list[FrameBundle]]],
        on_progress: Callable[[FrameBundle], None] | None,
    ) -> None:
        for scene, frames in scenes:
            for auditor in self.auditors:
                auditor.reset()

            audit_rows: list[dict[str, Any]] = []
            pending_images: list[tuple[str, str, bytes]] = []
            ordered = sorted(frames, key=lambda f: f.timestamp_us)
            self.store.save_scene(
                {
                    "scene_token": scene.token,
                    "name": scene.name,
                    "description": scene.description,
                    "weather": scene.weather,
                    "time_of_day": scene.time_of_day,
                    "nbr_samples": len(ordered),
                }
            )
            for bundle in ordered:
                findings = FrameFindings(bundle)
                for auditor in self.auditors:
                    auditor.audit_sample(bundle, findings)
                for r in findings.boxes:
                    r.finalize_severity()

                assert findings.health is not None
                self.store.save_sample(findings.health.to_row(bundle))
                audit_rows.extend(r.to_row(bundle.sample_token) for r in findings.boxes)
                if self.save_images:
                    for variant, jpeg in build_frame_overlays(bundle, findings.boxes).items():
                        pending_images.append((bundle.sample_token, variant, jpeg))
                if on_progress:
                    on_progress(bundle)

            self.store.save_audit_results(audit_rows)
            for token, variant, jpeg in pending_images:
                self.store.save_image(token, variant, jpeg)


def run_audit(
    scenes: Iterable[tuple[SceneMeta, list[FrameBundle]]],
    store: AuditStore,
    save_images: bool = True,
    on_progress: Callable[[FrameBundle], None] | None = None,
    clear: bool = False,
) -> None:
    """Convenience wrapper: run the default pipeline over `scenes`."""
    AuditPipeline(store, save_images=save_images).run(scenes, on_progress, clear=clear)
