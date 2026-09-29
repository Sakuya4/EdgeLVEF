"""Non-accumulating periodic AI scheduler."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, List, Optional

from ai.engine_base import AnalysisEngine
from ai.result import AnalysisResult
from .frame_buffer import BufferedFrame, FrameRingBuffer


class AnalysisScheduler:
    def __init__(
        self,
        frame_buffer: FrameRingBuffer,
        engine: AnalysisEngine,
        fps: float,
        required_seconds: float,
        interval_seconds: float,
        on_started: Callable[[List[BufferedFrame]], None],
        on_result: Callable[[AnalysisResult], None],
    ) -> None:
        self.frame_buffer = frame_buffer
        self.engine = engine
        self.fps = fps
        self.required_seconds = required_seconds
        self.interval_seconds = interval_seconds
        self.on_started = on_started
        self.on_result = on_result
        self._stop = threading.Event()
        self._busy = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ai-worker")

    @property
    def busy(self) -> bool:
        return self._busy.is_set()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="analysis-scheduler", daemon=False)
        self._thread.start()

    def _run(self) -> None:
        # Check promptly while collecting, then settle into the configured cadence.
        while not self._stop.wait(min(0.25, self.interval_seconds)):
            if len(self.frame_buffer) < self.frame_buffer.max_frames:
                continue
            break
        next_run = time.monotonic()
        while not self._stop.is_set():
            delay = next_run - time.monotonic()
            if delay > 0 and self._stop.wait(delay):
                break
            next_run += self.interval_seconds
            if self._busy.is_set():
                continue  # Explicitly skip; never accumulate inference jobs.
            snapshot = self.frame_buffer.snapshot()
            if not snapshot:
                continue
            self._busy.set()
            self.on_started(snapshot)
            future = self._executor.submit(
                self.engine.analyze, (item.frame for item in snapshot), self.fps
            )
            future.add_done_callback(self._completed)

    def _completed(self, future) -> None:
        try:
            result = future.result()
        except Exception as exc:  # Defensive: engine normally converts failures.
            result = AnalysisResult("", False, error=str(exc))
        self._busy.clear()
        self.on_result(result)

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._executor.shutdown(wait=True, cancel_futures=True)
