"""Analysis contract shared by the scheduler and interchangeable adapters."""

from __future__ import annotations

from typing import Iterable, Protocol

import numpy as np

from .result import AnalysisResult


class AnalysisEngine(Protocol):
    def analyze(self, frames: Iterable[np.ndarray], fps: float) -> AnalysisResult:
        """Analyze a cine in a worker thread and return a UI-neutral result."""

