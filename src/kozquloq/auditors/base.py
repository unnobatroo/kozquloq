"""Auditor contract.

Auditors run per keyframe in pipeline order and share one `FrameFindings`:
the geometric auditor populates `boxes`, the kinematic auditor refines those
results in place, the sensor-health auditor reads them. `reset()` runs once
per scene so stateful auditors drop cross-scene tracking history.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kozquloq.auditors.geometry import BoxAuditResult
    from kozquloq.auditors.sensor_health import SampleHealth
    from kozquloq.types import FrameBundle


@dataclass
class FrameFindings:
    """Mutable accumulator for one keyframe's audit output."""

    bundle: FrameBundle
    boxes: list[BoxAuditResult] = field(default_factory=list)
    health: SampleHealth | None = None


class BaseAuditor(ABC):
    """One audit subsystem. Implementations write into `findings`."""

    @abstractmethod
    def audit_sample(self, bundle: FrameBundle, findings: FrameFindings) -> None:
        """Audit one keyframe, recording results into `findings`."""

    def reset(self) -> None:  # noqa: B027 -- intentional no-op hook
        """Clear per-scene state. Stateless auditors need nothing."""
