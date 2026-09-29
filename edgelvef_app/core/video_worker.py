"""Source-aware acquisition worker and latest-frame mailbox."""

from __future__ import annotations

import queue
import threading
import time
import math
from collections import deque
from typing import Callable, Optional

import numpy as np

from sources.source_base import UltrasoundSource
from .frame_buffer import FrameRingBuffer


class VideoWorker:
    def __init__(
        self,
        source: UltrasoundSource,
        frame_buffer: FrameRingBuffer,
        fps: float,
        on_error: Callable[[str], None],
        source_fps: Optional[float] = None,
    ) -> None:
        self.source = source
        self.frame_buffer = frame_buffer
        self.fps = fps
        self.source_fps = fps if source_fps is None else source_fps
        self.requires_external_pacing = getattr(source, "requires_external_pacing", True)
        self.on_error = on_error
        self.latest: queue.Queue[np.ndarray] = queue.Queue(maxsize=1)
        self._acquisition_times = deque()
        self._stats_lock = threading.Lock()
        self._last_buffer_timestamp = float("-inf")
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="video-worker", daemon=False)
        self._thread.start()

    def _publish_latest(self, frame: np.ndarray) -> None:
        try:
            self.latest.put_nowait(frame)
        except queue.Full:
            try:
                self.latest.get_nowait()
            except queue.Empty:
                pass
            try:
                self.latest.put_nowait(frame)
            except queue.Full:
                pass

    def acquisition_fps(self, window_seconds: float = 2.0) -> float:
        """Sliding FPS of successful decoded frames, never GUI render FPS."""
        now = time.monotonic()
        with self._stats_lock:
            self._trim_acquisition_times(now, window_seconds)
            timestamps = list(self._acquisition_times)
        if len(timestamps) < 2:
            return 0.0
        elapsed = timestamps[-1] - timestamps[0]
        return (len(timestamps) - 1) / elapsed if elapsed > 0 else 0.0

    def _trim_acquisition_times(self, now: float, window_seconds: float) -> None:
        cutoff = now - window_seconds
        while self._acquisition_times and self._acquisition_times[0] < cutoff:
            self._acquisition_times.popleft()

    def _log_diagnostics(self) -> None:
        loops = getattr(self.source, "loop_count", None)
        loop_text = f" | Loops: {loops}" if loops is not None else ""
        source_text = (
            f"{self.source_fps:.1f}"
            if self.source_fps > 0
            else f"unavailable (fallback {self.fps:.1f})"
        )
        print(
            f"Source FPS: {source_text} | "
            f"Acquisition FPS: {self.acquisition_fps():.1f} | "
            f"Buffer: {len(self.frame_buffer)} frames / "
            f"{self.frame_buffer.duration():.1f} s"
            f"{loop_text}",
            flush=True,
        )

    def _run(self) -> None:
        period = 1.0 / self.fps
        deadline = time.monotonic()
        next_log = deadline + 3.0
        consecutive_misses = 0
        try:
            while not self._stop.is_set():
                frame = self.source.read()
                if frame is None:
                    consecutive_misses += 1
                    if consecutive_misses == 30 or consecutive_misses % 300 == 0:
                        print(
                            f"Video acquisition waiting: {consecutive_misses} consecutive read misses; retrying",
                            flush=True,
                        )
                    self._stop.wait(min(period, 0.1))
                    continue
                consecutive_misses = 0
                now = time.monotonic()
                with self._stats_lock:
                    self._acquisition_times.append(now)
                    self._trim_acquisition_times(now, 2.0)
                stamp = max(now, math.nextafter(self._last_buffer_timestamp, math.inf))
                self._last_buffer_timestamp = stamp
                # Every decoded frame reaches AI before any GUI frame replacement.
                self.frame_buffer.append(frame, stamp)
                self._publish_latest(frame)
                if now >= next_log:
                    self._log_diagnostics()
                    next_log = now + 3.0
                if self.requires_external_pacing:
                    # Unpaced sources still use drift-resistant monotonic
                    # deadlines. Realtime-blocking sources proceed directly
                    # to their next read() without another per-frame wait.
                    deadline += period
                    delay = deadline - time.monotonic()
                    if delay > 0:
                        self._stop.wait(delay)
                    else:
                        deadline = time.monotonic()
        except Exception as exc:  # Keep the GTK process alive and show a useful error.
            if not self._stop.is_set():
                self.on_error(str(exc))

    def pop_latest(self) -> Optional[np.ndarray]:
        try:
            return self.latest.get_nowait()
        except queue.Empty:
            return None

    def stop(self) -> None:
        self._stop.set()
        self.source.close()
        if self._thread and self._thread.is_alive():
            self._thread.join()
