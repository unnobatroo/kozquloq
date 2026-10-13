"""End-to-end audit pipeline: frames -> auditors -> store rows (+ overlays).

Auditors and the storage backend are injected (dependency inversion): the
orchestrator only knows the `BaseAuditor` and `AuditStore` contracts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from kozquloq.auditors import DEFAULT_AUDITORS, BaseAuditor, FrameFindings

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence
    from pathlib import Path

    from kozquloq.storage.base import AuditStore
    from kozquloq.types import FrameBundle, SceneMeta


class AuditPipeline:
    def __init__(
        self,
        store: AuditStore,
        auditors: Sequence[BaseAuditor] | None = None,
        viz_dir: str | Path | None = None,
    ) -> None:
        self.store = store
        self.auditors = list(auditors) if auditors else [c() for c in DEFAULT_AUDITORS]
        self.viz_dir = viz_dir

    def run(
        self,
        scenes: Iterable[tuple[SceneMeta, list[FrameBundle]]],
        on_progress: Callable[[FrameBundle], None] | None = None,
        clear: bool = False,
    ) -> None:
        """Audit every scene and persist sample/audit rows atomically.

        An interruption rolls back instead of leaving a partially-written
        (and misleadingly clean-looking) audit.
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
            ordered = sorted(frames, key=lambda f: f.timestamp_us)
            for bundle in ordered:
                findings = FrameFindings(bundle)
                for auditor in self.auditors:
                    auditor.audit_sample(bundle, findings)
                for r in findings.boxes:
                    r.finalize_severity()

                assert findings.health is not None
                self.store.save_sample(findings.health.to_row(bundle, scene))
                audit_rows.extend(r.to_row(bundle.sample_token) for r in findings.boxes)
                if self.viz_dir is not None and any(r.flagged for r in findings.boxes):
                    from kozquloq.visualization.overlay import save_annotated_frame

                    save_annotated_frame(bundle, findings.boxes, self.viz_dir)
                if on_progress:
                    on_progress(bundle)

            self.store.save_audits(audit_rows)


def run_audit(
    scenes: Iterable[tuple[SceneMeta, list[FrameBundle]]],
    store: AuditStore,
    viz_dir: str | Path | None = None,
    on_progress: Callable[[FrameBundle], None] | None = None,
    clear: bool = False,
) -> None:
    """Convenience wrapper: run the default pipeline over `scenes`."""
    AuditPipeline(store, viz_dir=viz_dir).run(scenes, on_progress, clear=clear)
