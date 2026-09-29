"""Thread-safe lifetime statistics for one measurement session."""

from __future__ import annotations

import math
import numbers
import threading
from typing import Optional


class MeasurementSession:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self._count = 0
            self._total = 0.0
            self._maximum: Optional[float] = None
            self._minimum: Optional[float] = None

    def update(self, lvef) -> bool:
        """Add one finite, numeric 0..100 LVEF value; reject everything else."""
        if isinstance(lvef, bool) or not isinstance(lvef, numbers.Real):
            return False
        value = float(lvef)
        if not math.isfinite(value) or not 0.0 <= value <= 100.0:
            return False
        with self._lock:
            self._count += 1
            self._total += value
            self._maximum = value if self._maximum is None else max(self._maximum, value)
            self._minimum = value if self._minimum is None else min(self._minimum, value)
        return True

    @property
    def maximum(self) -> Optional[float]:
        with self._lock:
            return self._maximum

    @property
    def minimum(self) -> Optional[float]:
        with self._lock:
            return self._minimum

    @property
    def average(self) -> Optional[float]:
        with self._lock:
            return self._total / self._count if self._count else None

    @property
    def count(self) -> int:
        with self._lock:
            return self._count
