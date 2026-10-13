"""Audit subsystems and the per-frame audit pipeline."""

from kozquloq.auditors.base import BaseAuditor, FrameFindings
from kozquloq.auditors.geometry import BoxAuditResult, GeometricAuditor
from kozquloq.auditors.kinematics import KinematicAuditor, KinematicTracker
from kozquloq.auditors.sensor_health import SampleHealth, SensorHealthAuditor
from kozquloq.types import FrameBundle

DEFAULT_AUDITORS: tuple[type[BaseAuditor], ...] = (
    GeometricAuditor,
    KinematicAuditor,
    SensorHealthAuditor,
)


def audit_frame(
    bundle: FrameBundle, auditors: list[BaseAuditor] | None = None
) -> tuple[SampleHealth, list[BoxAuditResult]]:
    """Run geometric, kinematic and sensor-health audits on one keyframe."""
    findings = FrameFindings(bundle)
    for auditor in auditors or [cls() for cls in DEFAULT_AUDITORS]:
        auditor.audit_sample(bundle, findings)
    for r in findings.boxes:
        r.finalize_severity()
    assert findings.health is not None
    return findings.health, findings.boxes


__all__ = [
    "BaseAuditor",
    "BoxAuditResult",
    "FrameFindings",
    "GeometricAuditor",
    "KinematicAuditor",
    "KinematicTracker",
    "SampleHealth",
    "SensorHealthAuditor",
    "audit_frame",
]
