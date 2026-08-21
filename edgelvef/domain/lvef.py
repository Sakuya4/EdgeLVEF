from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FrozenEdgeHead:
    intercept: float
    global_fs_slope: float
    low_ef_score_threshold: float
    low_ef_definition: float = 40.0

    def estimate_lvef(self, global_fs: float) -> float:
        return self.intercept + self.global_fs_slope * global_fs

    def low_ef_score(self, global_fs: float) -> float:
        return -global_fs

    def predicts_low_ef(self, global_fs: float) -> bool:
        return self.low_ef_score(global_fs) >= self.low_ef_score_threshold
