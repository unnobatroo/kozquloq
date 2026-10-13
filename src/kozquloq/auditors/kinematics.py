"""Kinematic & temporal tracking auditor (spec §3.3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from kozquloq.auditors.base import BaseAuditor, FrameFindings
from kozquloq.constants import (
    DEFAULT_ACCEL_MAX_MPS2,
    PEDESTRIAN_ACCEL_MAX_MPS2,
    PEDESTRIAN_PREFIXES,
    RIGID_PREFIXES,
    SCALE_VARIANCE_MAX,
    VEHICLE_ACCEL_MAX_MPS2,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from kozquloq.auditors.geometry import BoxAuditResult
    from kozquloq.types import FrameBundle


def accel_threshold(category: str) -> float:
    if category.startswith(PEDESTRIAN_PREFIXES):
        return PEDESTRIAN_ACCEL_MAX_MPS2
    if category.startswith("vehicle."):
        return VEHICLE_ACCEL_MAX_MPS2
    return DEFAULT_ACCEL_MAX_MPS2


def is_rigid(category: str) -> bool:
    return category.startswith(RIGID_PREFIXES)


@dataclass
class _Hist:
    t: float
    pos: NDArray[np.float64]
    volume: float
    vel: NDArray[np.float64] | None


class KinematicTracker:
    """Per-instance temporal state across consecutive keyframes."""

    def __init__(self) -> None:
        self._history: dict[str, _Hist] = {}

    def update(self, result: BoxAuditResult, t_s: float) -> None:
        pos = result.center_global
        volume = result.volume_m3
        vel: NDArray[np.float64] | None = None

        prev = self._history.get(result.instance_token)
        if prev is not None:
            dt = t_s - prev.t
            if dt > 1e-6:
                vel = (pos - prev.pos) / dt
                result.velocity_mps = round(float(np.linalg.norm(vel)), 4)

                if prev.vel is not None:
                    accel = float(np.linalg.norm((vel - prev.vel) / dt))
                    result.acceleration_mps2 = round(accel, 4)
                    result.is_kinematic_outlier = accel > accel_threshold(result.category)

                dv = abs(volume - prev.volume) / max(volume, prev.volume)
                result.volume_variance_ratio = round(float(dv), 4)
                if is_rigid(result.category):
                    result.is_scale_unstable = dv > SCALE_VARIANCE_MAX

        self._history[result.instance_token] = _Hist(t_s, pos, volume, vel)


class KinematicAuditor(BaseAuditor):
    """Per-instance temporal consistency audit across keyframes (spec §3.3)."""

    def __init__(self) -> None:
        self._tracker = KinematicTracker()

    def audit_sample(self, bundle: FrameBundle, findings: FrameFindings) -> None:
        t_s = bundle.timestamp_us / 1e6
        for result in findings.boxes:
            self._tracker.update(result, t_s)

    def reset(self) -> None:
        self._tracker = KinematicTracker()
