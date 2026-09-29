"""A bounded, time-based ring buffer with explicit frame ownership."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from typing import Deque, List

import numpy as np


@dataclass(frozen=True)
class BufferedFrame:
    timestamp: float
    frame: np.ndarray


class FrameRingBuffer:
    def __init__(self, seconds: float, fps: float) -> None:
        if seconds <= 0 or fps <= 0:
            raise ValueError("seconds and fps must be positive")
        self.seconds = float(seconds)
        self.max_frames = max(2, int(round(seconds * fps)))
        self._frames: Deque[BufferedFrame] = deque(maxlen=self.max_frames)
        self._lock = threading.Lock()

    def append(self, frame: np.ndarray, timestamp: float) -> None:
        owned = np.ascontiguousarray(frame).copy()
        with self._lock:
            self._frames.append(BufferedFrame(float(timestamp), owned))
            cutoff = timestamp - self.seconds
            while len(self._frames) > 1 and self._frames[0].timestamp < cutoff:
                self._frames.popleft()

    def snapshot(self) -> List[BufferedFrame]:
        with self._lock:
            return [BufferedFrame(item.timestamp, item.frame.copy()) for item in self._frames]

    def clear(self) -> None:
        with self._lock:
            self._frames.clear()

    def duration(self) -> float:
        with self._lock:
            if len(self._frames) < 2:
                return 0.0
            return self._frames[-1].timestamp - self._frames[0].timestamp

    def __len__(self) -> int:
        with self._lock:
            return len(self._frames)
