"""GTK-independent video discovery and serialized source lifecycle."""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from sources.video_source import TestVideoSource
from .frame_buffer import FrameRingBuffer
from .video_worker import VideoWorker

SUPPORTED_EXTENSIONS = {".avi", ".mp4", ".mov", ".mkv"}


def discover_videos(directory: Path):
    """List candidates only; codec usability is checked when opening a video."""
    if not directory.is_dir():
        return []
    return sorted(
        (path for path in directory.iterdir()
         if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS),
        key=lambda path: path.name,
    )


@dataclass
class VideoSession:
    path: Path
    buffer: FrameRingBuffer
    worker: VideoWorker
    fps: float


class VideoSessionManager:
    """Call switch/stop from a background thread, never the GTK thread."""

    def __init__(self, seconds: float, fallback_fps: float, source_factory=TestVideoSource):
        self.seconds = seconds
        self.fallback_fps = fallback_fps
        self.source_factory = source_factory
        self.current: Optional[VideoSession] = None
        self._lock = threading.Lock()

    def _dispose(self, session: VideoSession) -> None:
        session.worker.stop()
        while session.worker.pop_latest() is not None:
            pass
        session.buffer.clear()

    def _open(self, path: Path, on_error: Callable[[str], None]) -> VideoSession:
        source = self.source_factory(path)
        try:
            source.open()
            metadata_fps = source.get_fps()
            fps = metadata_fps if math.isfinite(metadata_fps) and metadata_fps > 0 else self.fallback_fps
            # Open success alone does not prove that the board has this codec.
            first_frame = source.read()
            if first_frame is None:
                raise RuntimeError("No decodable first frame")
            buffer = FrameRingBuffer(self.seconds, fps)
            worker = VideoWorker(source, buffer, fps, on_error, source_fps=metadata_fps)
            stamp = time.monotonic()
            buffer.append(first_frame, stamp)
            worker._last_buffer_timestamp = stamp
            worker.latest.put_nowait(first_frame)
            session = VideoSession(path, buffer, worker, fps)
            worker.start()
            return session
        except Exception:
            source.close()
            raise

    def switch(self, path: Path, on_error: Callable[[str], None]):
        """Return (session, error); failed switches try reopening previous video.

        Even rollback receives a fresh buffer so no cross-video frames survive.
        """
        with self._lock:
            previous = self.current
            self.current = None
            if previous:
                self._dispose(previous)
            try:
                self.current = self._open(path, on_error)
                return self.current, None
            except Exception as exc:
                print(f"Failed to open video: {path.name}: {exc}", flush=True)
                if previous and previous.path != path:
                    try:
                        self.current = self._open(previous.path, on_error)
                    except Exception as rollback_exc:
                        print(f"Video rollback failed: {rollback_exc}", flush=True)
                return self.current, str(exc)

    def stop(self) -> None:
        with self._lock:
            if self.current:
                self._dispose(self.current)
                self.current = None
