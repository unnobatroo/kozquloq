"""Feature transforms for the quality dataset."""

from __future__ import annotations

from typing import TYPE_CHECKING

import torch

if TYPE_CHECKING:
    from collections.abc import Callable


class Normalize:
    def __init__(self, mean: torch.Tensor, std: torch.Tensor) -> None:
        self.mean = mean
        self.std = std.clamp_min(1e-6)

    @classmethod
    def from_rows(cls, rows: list[torch.Tensor]) -> Normalize:
        stacked = torch.stack(rows)
        return cls(stacked.mean(0), stacked.std(0))

    def __call__(self, feats: torch.Tensor) -> torch.Tensor:
        return (feats - self.mean) / self.std


def compose(
    *transforms: Callable[[torch.Tensor], torch.Tensor],
) -> Callable[[torch.Tensor], torch.Tensor]:
    def apply(x: torch.Tensor) -> torch.Tensor:
        for t in transforms:
            x = t(x)
        return x

    return apply
