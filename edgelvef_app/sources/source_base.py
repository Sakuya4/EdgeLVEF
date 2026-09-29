"""Source abstraction kept independent from GTK and EdgeLVEF."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import numpy as np


class UltrasoundSource(ABC):
    @property
    def requires_external_pacing(self) -> bool:
        """True when the worker must pace successful reads to ``get_fps()``.

        A source whose ``read()`` already blocks at its realtime cadence should
        override this to False. Unknown/future sources retain worker pacing.
        """
        return True

    @abstractmethod
    def open(self) -> None:
        """Open the stream or raise a descriptive exception."""

    @abstractmethod
    def read(self) -> Optional[np.ndarray]:
        """Return one BGR uint8 frame, or None for a recoverable read miss."""

    @abstractmethod
    def close(self) -> None:
        """Release source resources; safe to call more than once."""

    @abstractmethod
    def get_fps(self) -> float:
        """Return source FPS, or a non-positive value when unavailable."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable source name."""
