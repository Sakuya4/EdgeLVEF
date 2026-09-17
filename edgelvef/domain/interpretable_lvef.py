from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MonotonicLvefCalibration:
    intercept: float
    scale: float
    exponent: float
    low_ef_definition: float = 40.0
    ratio_min: float = 0.3267
    ratio_max: float = 0.8072

    def estimate(self, lvidd: float, lvids: float) -> dict[str, float | bool]:
        if not np.isfinite(lvidd) or not np.isfinite(lvids) or lvidd <= 0:
            raise ValueError("LVIDd and LVIDs must be finite, with LVIDd greater than zero")
        ratio = float(lvids / lvidd)
        if not 0.20 <= ratio < 1.0:
            raise ValueError(f"Physiologically invalid LVIDs/LVIDd ratio: {ratio:.4f}")
        base = 100.0 * (1.0 - ratio**self.exponent)
        lvef = float(np.clip(self.intercept + self.scale * base, 0.0, 100.0))
        return {
            "lvidd_px": float(lvidd),
            "lvids_px": float(lvids),
            "lvid_ratio": ratio,
            "lvef_percent": lvef,
            "predicts_lvef_at_or_below_40": lvef <= self.low_ef_definition,
            "inside_development_ratio_range": self.ratio_min <= ratio <= self.ratio_max,
        }
