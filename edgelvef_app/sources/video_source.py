"""Looping OpenCV test-video source."""

from __future__ import annotations

import threading
import math
from pathlib import Path
from typing import Any, Optional

import numpy as np

from .source_base import UltrasoundSource


def _load_cv2():
    import cv2

    return cv2


class TestVideoSource(UltrasoundSource):
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._capture: Optional[Any] = None
        self._cv2: Optional[Any] = None
        self._lock = threading.Lock()
        self._fps = 0.0
        self._loop_count = 0
        self._closed = True

    @property
    def display_name(self) -> str:
        return "Test Video"

    @property
    def requires_external_pacing(self) -> bool:
        # FRDM i.MX93 GStreamer/AIUR VideoCapture.read() already blocks near
        # the AVI's realtime cadence; another worker wait causes double pacing.
        return False

    def open(self) -> None:
        if not self.path.is_file():
            raise FileNotFoundError(
                f"Test video not found: {self.path}. Place a PLAX AVI at test_data/plax.avi."
            )
        cv2 = _load_cv2()
        capture = cv2.VideoCapture(str(self.path))
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(f"OpenCV could not open video: {self.path}")
        with self._lock:
            old_capture = self._capture
            self._capture = capture
            self._cv2 = cv2
            self._closed = False
            source_fps = float(capture.get(cv2.CAP_PROP_FPS))
            if math.isfinite(source_fps) and source_fps > 0:
                self._fps = source_fps
        if old_capture is not None:
            old_capture.release()

    def read(self) -> Optional[np.ndarray]:
        with self._lock:
            capture = self._capture
            if capture is None:
                if self._closed:
                    raise RuntimeError("Video source is not open")
                return self._reopen_locked()
            ok, frame = capture.read()
            if ok and frame is not None:
                return frame

            # GStreamer/AIUR AVI seeking is unreliable on the target board.
            # Release and reopen only the capture; GTK and workers stay alive.
            capture.release()
            self._capture = None
            return self._reopen_locked()

    def _reopen_locked(self) -> Optional[np.ndarray]:
        replacement = self._cv2.VideoCapture(str(self.path))
        if not replacement.isOpened():
            replacement.release()
            return None
        self._capture = replacement
        ok, frame = replacement.read()
        if ok and frame is not None:
            self._loop_count += 1
            return frame
        return None

    def close(self) -> None:
        with self._lock:
            capture, self._capture = self._capture, None
            self._closed = True
        if capture is not None:
            capture.release()

    def get_fps(self) -> float:
        with self._lock:
            return self._fps

    @property
    def loop_count(self) -> int:
        with self._lock:
            return self._loop_count
