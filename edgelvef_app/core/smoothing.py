"""Median smoothing for valid LVEF measurements."""

from __future__ import annotations

import statistics
from collections import deque
from typing import Deque, Optional


class LVEFSmoother:
    def __init__(self, window_size: int = 3) -> None:
        if window_size < 1:
            raise ValueError("window_size must be at least 1")
        self._values: Deque[float] = deque(maxlen=window_size)

    def add(self, value: float) -> float:
        numeric = float(value)
        if not 0.0 <= numeric <= 100.0:
            raise ValueError("LVEF must be between 0 and 100")
        self._values.append(numeric)
        return float(statistics.median(self._values))

    @property
    def value(self) -> Optional[float]:
        return float(statistics.median(self._values)) if self._values else None

