from __future__ import annotations

import sys
import threading
import time
import types
import queue
from unittest.mock import patch
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.lvef_engine import EdgeLVEFEngine, PythonAPIBackend
from core.frame_buffer import FrameRingBuffer
from core.scheduler import AnalysisScheduler
from core.smoothing import LVEFSmoother
from core.video_worker import VideoWorker
from ai.result import AnalysisResult
import config


class FrameBufferTests(unittest.TestCase):
    def test_is_bounded_and_owns_frames(self):
        buffer = FrameRingBuffer(seconds=1, fps=2)
        frame = np.zeros((2, 2, 3), dtype=np.uint8)
        for index in range(5):
            frame.fill(index)
            buffer.append(frame, float(index))
        self.assertLessEqual(len(buffer), 2)
        frame.fill(99)
        self.assertNotEqual(int(buffer.snapshot()[-1].frame[0, 0, 0]), 99)

    def test_source_fps_controls_five_second_capacity(self):
        self.assertEqual(FrameRingBuffer(5, 30).max_frames, 150)
        self.assertEqual(FrameRingBuffer(5, 25).max_frames, 125)


class VideoSourceTests(unittest.TestCase):
    def test_source_pacing_capabilities(self):
        from sources.probe_source import ProbeSource
        from sources.video_source import TestVideoSource

        self.assertFalse(TestVideoSource(ROOT / "test_data" / "plax.avi").requires_external_pacing)
        self.assertTrue(ProbeSource().requires_external_pacing)

    def test_missing_video_has_descriptive_error(self):
        from sources.video_source import TestVideoSource

        with self.assertRaisesRegex(FileNotFoundError, "test_data/plax.avi"):
            TestVideoSource(ROOT / "test_data" / "missing.avi").open()

    def test_eof_reopens_capture_repeatedly_without_seek(self):
        captures = []

        class FakeCapture:
            def __init__(self, path):
                self.path = path
                self.read_count = 0
                self.released = False
                captures.append(self)

            def isOpened(self):
                return True

            def read(self):
                self.read_count += 1
                if self.read_count == 1:
                    value = len(captures)
                    return True, np.full((2, 2, 3), value, dtype=np.uint8)
                return False, None

            def set(self, _prop, _value):
                raise AssertionError("AVI loop must not use frame seek")

            def get(self, _prop):
                return 25.0

            def release(self):
                self.released = True

        fake_cv2 = types.SimpleNamespace(
            VideoCapture=FakeCapture, CAP_PROP_FPS=2
        )
        with patch("sources.video_source._load_cv2", return_value=fake_cv2):
            from sources.video_source import TestVideoSource

            source = TestVideoSource(ROOT / "README.md")
            source.open()
            values = [int(source.read()[0, 0, 0]) for _ in range(5)]
            source.close()
        self.assertEqual(values, [1, 2, 3, 4, 5])
        self.assertEqual(source.loop_count, 4)
        self.assertTrue(all(capture.released for capture in captures))

    def test_worker_continues_across_eof_and_stops_cleanly(self):
        captures = []

        class FakeCapture:
            def __init__(self, _path):
                self.read_count = 0
                captures.append(self)

            def isOpened(self):
                return True

            def read(self):
                self.read_count += 1
                if self.read_count == 1:
                    time.sleep(0.002)  # Model a realtime-blocking capture.
                    return True, np.full((2, 2, 3), len(captures), dtype=np.uint8)
                return False, None

            def get(self, _prop):
                return 40.0

            def release(self):
                pass

        fake_cv2 = types.SimpleNamespace(VideoCapture=FakeCapture, CAP_PROP_FPS=2)
        with patch("sources.video_source._load_cv2", return_value=fake_cv2):
            from sources.video_source import TestVideoSource

            source = TestVideoSource(ROOT / "README.md")
            source.open()
            buffer = FrameRingBuffer(0.5, source.get_fps())
            errors = []
            worker = VideoWorker(source, buffer, source.get_fps(), errors.append)
            worker.start()
            try:
                time.sleep(0.16)
                self.assertTrue(worker._thread.is_alive())
                self.assertGreaterEqual(source.loop_count, 3)
                timestamps = [item.timestamp for item in buffer.snapshot()]
                self.assertEqual(timestamps, sorted(timestamps))
                self.assertTrue(all(left < right for left, right in zip(timestamps, timestamps[1:])))
            finally:
                worker.stop()
        self.assertFalse(worker._thread.is_alive())
        self.assertEqual(errors, [])


class VideoWorkerTests(unittest.TestCase):
    def test_successful_read_pacing_is_source_selectable(self):
        class ThreeFrameSource:
            def __init__(self, requires_external_pacing):
                self.requires_external_pacing = requires_external_pacing
                self.reads = 0
                self.worker = None

            def read(self):
                self.reads += 1
                if self.reads == 3:
                    self.worker._stop.set()
                return np.full((2, 2, 3), self.reads, dtype=np.uint8)

            def close(self):
                pass

        for externally_paced in (False, True):
            with self.subTest(externally_paced=externally_paced):
                source = ThreeFrameSource(externally_paced)
                buffer = FrameRingBuffer(1, 30)
                errors = []
                worker = VideoWorker(source, buffer, 30, errors.append)
                source.worker = worker
                waits = []
                with patch("core.video_worker.time.monotonic", return_value=1.0), patch.object(
                    worker._stop,
                    "wait",
                    side_effect=lambda delay: waits.append(delay) or False,
                ):
                    worker._run()
                self.assertEqual(
                    [int(item.frame[0, 0, 0]) for item in buffer.snapshot()], [1, 2, 3]
                )
                self.assertEqual(errors, [])
                if externally_paced:
                    self.assertEqual(len(waits), 3)
                    self.assertTrue(all(delay > 0 for delay in waits))
                else:
                    self.assertEqual(waits, [])

    def test_recoverable_read_misses_do_not_end_worker(self):
        class RecoveringSource:
            def __init__(self):
                self.reads = 0
                self.closed = False

            def read(self):
                self.reads += 1
                if self.reads <= 12:
                    return None
                return np.ones((2, 2, 3), dtype=np.uint8)

            def close(self):
                self.closed = True

        source = RecoveringSource()
        buffer = FrameRingBuffer(0.5, 100)
        errors = []
        worker = VideoWorker(source, buffer, 100, errors.append)
        worker.start()
        try:
            deadline = time.monotonic() + 1.0
            while len(buffer) == 0 and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(worker._thread.is_alive())
            self.assertGreaterEqual(len(buffer), 1)
        finally:
            worker.stop()
        self.assertTrue(source.closed)
        self.assertFalse(worker._thread.is_alive())
        self.assertEqual(errors, [])

    def test_ai_buffer_receives_frames_even_if_gui_mailbox_is_full(self):
        class FakeSource:
            def __init__(self):
                self.number = 0
                self.closed = False

            def read(self):
                self.number += 1
                return np.full((2, 2, 3), self.number, dtype=np.uint8)

            def close(self):
                self.closed = True

        class AlwaysFullMailbox:
            def put_nowait(self, _frame):
                raise queue.Full

            def get_nowait(self):
                raise queue.Empty

        source = FakeSource()
        buffer = FrameRingBuffer(0.3, 50)
        errors = []
        worker = VideoWorker(source, buffer, 50, errors.append)
        worker.latest = AlwaysFullMailbox()
        worker.start()
        time.sleep(0.12)
        worker.stop()
        self.assertGreaterEqual(len(buffer), 4)
        self.assertGreater(worker.acquisition_fps(), 0)
        self.assertTrue(source.closed)
        self.assertFalse(worker._thread.is_alive())
        self.assertEqual(errors, [])


class SmoothingTests(unittest.TestCase):
    def test_median_of_three(self):
        smoother = LVEFSmoother(3)
        smoother.add(51)
        smoother.add(58)
        self.assertEqual(smoother.add(53), 53)


class ParsingTests(unittest.TestCase):
    def test_json_output(self):
        payload = EdgeLVEFEngine._parse_output('{"lvef": 54, "global_fs": 28}')
        result = EdgeLVEFEngine._result_from_payload("now", payload)
        self.assertTrue(result.success)
        self.assertEqual(result.lvef, 54)

    def test_text_output(self):
        payload = EdgeLVEFEngine._parse_output("LVEF: 52.5%\nGlobal FS = 26.1")
        self.assertEqual(payload["lvef"], 52.5)


class DeploymentTests(unittest.TestCase):
    def test_paths_are_anchored_to_main_directory(self):
        self.assertEqual(config.TEST_VIDEO_PATH, ROOT / "test_data" / "plax.avi")
        self.assertEqual(config.SAVED_DIR, ROOT / "saved")
        self.assertEqual(config.project_path("other.mp4"), ROOT / "other.mp4")

    def test_python_backend_is_injected_without_scheduler_change(self):
        expected = AnalysisResult("now", True, lvef=54)
        backend = PythonAPIBackend(lambda frames, fps: expected)
        engine = EdgeLVEFEngine(["edgelvef-analyze", "{video}"], 10, "CPUExecutionProvider", backend)
        self.assertIs(engine.analyze([], 30), expected)

    def test_missing_cli_is_deferred_to_analysis_error(self):
        frame = np.zeros((2, 2, 3), dtype=np.uint8)
        engine = EdgeLVEFEngine(["missing-edgelvef-cli", "{video}"], 10, "CPUExecutionProvider")
        with patch("ai.lvef_engine.CLIAnalysisBackend.encode_video"), patch(
            "ai.lvef_engine.subprocess.run", side_effect=FileNotFoundError("not installed")
        ):
            result = engine.analyze([frame, frame], 30)
        self.assertFalse(result.success)
        self.assertIn("EdgeLVEF CLI not available", result.error)


class SchedulerTests(unittest.TestCase):
    def test_slow_jobs_do_not_accumulate_or_overlap(self):
        class SlowEngine:
            def __init__(self):
                self.calls = 0
                self.concurrent = 0
                self.max_concurrent = 0
                self.lock = threading.Lock()

            def analyze(self, frames, fps):
                list(frames)
                with self.lock:
                    self.calls += 1
                    self.concurrent += 1
                    self.max_concurrent = max(self.max_concurrent, self.concurrent)
                time.sleep(0.12)
                with self.lock:
                    self.concurrent -= 1
                return AnalysisResult("now", True, lvef=50)

        buffer = FrameRingBuffer(seconds=0.1, fps=20)
        frame = np.zeros((2, 2, 3), dtype=np.uint8)
        buffer.append(frame, 0.0)
        buffer.append(frame, 0.05)
        engine = SlowEngine()
        results = []
        scheduler = AnalysisScheduler(
            buffer, engine, 20, 0.1, 0.03, lambda _snapshot: None, results.append
        )
        scheduler.start()
        time.sleep(0.22)
        scheduler.stop()
        self.assertEqual(engine.max_concurrent, 1)
        self.assertLessEqual(engine.calls, 2)
        self.assertEqual(len(results), engine.calls)


if __name__ == "__main__":
    unittest.main()
