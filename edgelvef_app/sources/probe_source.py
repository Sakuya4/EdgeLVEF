"""Extension point for the future wireless ultrasound probe."""

from __future__ import annotations

from typing import Optional

import numpy as np

from .source_base import UltrasoundSource


class ProbeSource(UltrasoundSource):
    """No vendor protocol is assumed until the actual model/SDK is known."""

    @property
    def display_name(self) -> str:
        return "Wireless Probe"

    def open(self) -> None:
        raise NotImplementedError("Probe model, Linux SDK, and Wi-Fi protocol are not available")

    def read(self) -> Optional[np.ndarray]:
        raise NotImplementedError("Probe frame acquisition is not implemented")

    def close(self) -> None:
        return None

    def get_fps(self) -> float:
        return 0.0

