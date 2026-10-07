"""480x320 fullscreen instrument UI; GTK access stays on the main thread."""

from __future__ import annotations

import threading
import time
from typing import Optional

import cv2
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk

import config
from ai.lvef_engine import EdgeLVEFEngine
from ai.result import AnalysisResult
from core.measurement_session import MeasurementSession
from core.scheduler import AnalysisScheduler
from core.video_session import VideoSessionManager
from core.video_worker import VideoWorker
from gpio.reset_button import GPIOResetButton, dispatch_reset_key
from ui.instrument_layout import STATS_HEIGHT


CSS = b"""
window { background: #000000; color: #ffffff; }
.stats { background: #101820; }
.stat-cell { border-left: 1px solid #40505d; padding: 4px 2px; }
.stat-first { padding: 4px 2px; }
.stat-title { color: #b7c3cc; font-size: 12px; font-weight: bold; }
.stat-value { color: #66e39a; font-size: 30px; font-weight: bold; }
"""


class ResponsiveVideoImage(Gtk.Image):
    def do_get_preferred_width(self):
        return 1, 1

    def do_get_preferred_height(self):
        return 1, 1

    def do_get_preferred_height_for_width(self, _width):
        return 1, 1

    def do_get_preferred_width_for_height(self, _height):
        return 1, 1


class MainWindow(Gtk.Window):
    def __init__(self) -> None:
        super().__init__(title="EdgeLVEF")
        self.set_default_size(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_can_focus(True)
        self.connect("delete-event", self._on_delete)
        self.connect("realize", self._hide_cursor)
        self.connect("key-press-event", self._on_key_press)

        self._closing = False
        self._started = False
        self._generation = 0
        self._switch_thread = None
        self._video_worker: Optional[VideoWorker] = None
        self._scheduler: Optional[AnalysisScheduler] = None
        self._render_count = 0
        self._render_log_at = 0
        if config.SOURCE_MODE == "aco_sidecar":
            from sources.aco_sidecar_source import AcoSidecarSource
            source_factory = lambda _path: AcoSidecarSource(
                config.SIDECAR_SOCKET, config.PROBE_FPS)
        elif config.SOURCE_MODE == "video":
            from sources.video_source import TestVideoSource
            source_factory = TestVideoSource
        else:
            raise ValueError(f"Unsupported EDGELVEF_SOURCE_MODE: {config.SOURCE_MODE}")
        self._sessions = VideoSessionManager(
            config.BUFFER_SECONDS, config.FALLBACK_FPS, source_factory
        )
        self._measurement = MeasurementSession()
        self._gpio = GPIOResetButton(
            config.RESET_BUTTON_GPIO_CHIP,
            config.RESET_BUTTON_GPIO_LINE,
            lambda: GLib.idle_add(self.on_reset_measurement),
            config.RESET_BUTTON_DEBOUNCE_SECONDS,
        )
        self._build_ui()
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        print(f"Instrument display configured: {config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT} fullscreen", flush=True)

    def _build_ui(self) -> None:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(root)
        self.video_image = ResponsiveVideoImage()
        self.video_image.set_hexpand(True)
        self.video_image.set_vexpand(True)
        viewer = Gtk.EventBox()
        viewer.modify_bg(Gtk.StateType.NORMAL, Gdk.color_parse("black"))
        viewer.add(self.video_image)
        overlay = Gtk.Overlay()
        overlay.add(viewer)
        self.connection_label = Gtk.Label(label="P42: waiting for on-board Sidecar" if config.SOURCE_MODE == "aco_sidecar" else "")
        self.connection_label.set_halign(Gtk.Align.START)
        self.connection_label.set_valign(Gtk.Align.START)
        self.connection_label.set_margin_start(6)
        self.connection_label.set_margin_top(4)
        overlay.add_overlay(self.connection_label)
        root.pack_start(overlay, True, True, 0)

        stats = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, homogeneous=True, spacing=0)
        stats.set_size_request(-1, STATS_HEIGHT)
        stats.get_style_context().add_class("stats")
        self.max_label = self._stat_cell(stats, "MAX LVEF", first=True)
        self.avg_label = self._stat_cell(stats, "AVG LVEF")
        self.min_label = self._stat_cell(stats, "MIN LVEF")
        root.pack_end(stats, False, False, 0)

    def _stat_cell(self, parent, title, first=False):
        cell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        cell.get_style_context().add_class("stat-first" if first else "stat-cell")
        heading = Gtk.Label(label=title)
        heading.get_style_context().add_class("stat-title")
        value = Gtk.Label(label="--")
        value.get_style_context().add_class("stat-value")
        cell.pack_start(heading, False, False, 0)
        cell.pack_start(value, True, True, 0)
        parent.pack_start(cell, True, True, 0)
        return value

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self.fullscreen()
        self.grab_focus()
        self._gpio.start()
        GLib.timeout_add(15, self._render_latest_frame)
        self._request_video(config.TEST_VIDEO_PATH)

    def _request_video(self, path) -> None:
        self._generation += 1
        generation = self._generation
        self._switch_thread = threading.Thread(
            target=self._open_video, args=(path, generation), name="video-start", daemon=False
        )
        self._switch_thread.start()

    def _open_video(self, path, generation) -> None:
        session, error = self._sessions.switch(
            path, lambda message: print(f"Video source error: {message}", flush=True)
        )
        GLib.idle_add(self._video_opened, generation, session, error)

    def _video_opened(self, generation, session, error) -> bool:
        if self._closing or generation != self._generation:
            return False
        if error or session is None:
            print(f"Failed to open {config.SOURCE_MODE} source: {error}", flush=True)
            return False
        self._video_worker = session.worker
        engine = EdgeLVEFEngine(
            config.ANALYZE_COMMAND, config.ANALYSIS_TIMEOUT_SECONDS, config.ONNX_PROVIDER
        )
        self._scheduler = AnalysisScheduler(
            session.buffer, engine, session.fps, config.BUFFER_SECONDS,
            config.ANALYSIS_INTERVAL_SECONDS, lambda _snapshot: None,
            lambda result: GLib.idle_add(self._analysis_finished, generation, result),
        )
        self._scheduler.start()
        print(
            f"{'Waiting for on-board Aco Sidecar' if config.SOURCE_MODE == 'aco_sidecar' else 'Playing test video: ' + session.path.name}",
            flush=True,
        )
        return False

    def _render_latest_frame(self) -> bool:
        if self._closing:
            return False
        if not self._video_worker:
            return True
        if config.SOURCE_MODE == "aco_sidecar":
            text = "P42: LIVE" if self._video_worker.source.is_live else "P42: waiting / reconnecting"
            if self.connection_label.get_text() != text:
                self.connection_label.set_text(text)
        frame = self._video_worker.pop_latest()
        if frame is None:
            return True
        allocation = self.video_image.get_allocation()
        max_w, max_h = max(allocation.width, 1), max(allocation.height, 1)
        height, width = frame.shape[:2]
        scale = min(max_w / width, max_h / height)
        target = (max(1, int(width * scale)), max(1, int(height * scale)))
        resized = cv2.resize(frame, target, interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        height, width = rgb.shape[:2]
        pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
            GLib.Bytes.new(rgb.tobytes()), GdkPixbuf.Colorspace.RGB, False, 8,
            width, height, width * 3
        )
        self.video_image.set_from_pixbuf(pixbuf)
        self._render_count += 1
        now = time.monotonic()
        if now >= self._render_log_at:
            print(f"UI_RENDERED: {self._render_count} source={config.SOURCE_MODE} acquisition_fps={self._video_worker.acquisition_fps():.1f}", flush=True)
            self._render_log_at = now + 10
        return True

    def _analysis_finished(self, generation, result: AnalysisResult) -> bool:
        if self._closing or generation != self._generation:
            return False
        if result.success and self._measurement.update(result.lvef):
            self._refresh_statistics()
        return False

    def _refresh_statistics(self) -> None:
        self.max_label.set_text(self._format_lvef(self._measurement.maximum))
        self.avg_label.set_text(self._format_lvef(self._measurement.average))
        self.min_label.set_text(self._format_lvef(self._measurement.minimum))

    @staticmethod
    def _format_lvef(value) -> str:
        return "--" if value is None else f"{value:.0f} %"

    def on_reset_measurement(self) -> bool:
        if not self._closing:
            self._measurement.reset()
            self._refresh_statistics()
            print("Measurement session reset", flush=True)
        return False

    def _on_key_press(self, _widget, event) -> bool:
        key_name = Gdk.keyval_name(event.keyval) or ""
        if dispatch_reset_key(key_name, self.on_reset_measurement):
            return True
        if key_name == "Escape":
            self.close()
            return True
        return False

    def _hide_cursor(self, *_args) -> None:
        window = self.get_window()
        if window:
            cursor = Gdk.Cursor.new_for_display(window.get_display(), Gdk.CursorType.BLANK_CURSOR)
            window.set_cursor(cursor)

    def _restore_cursor(self) -> None:
        window = self.get_window()
        if window:
            window.set_cursor(None)

    def _on_delete(self, *_args) -> bool:
        if self._closing:
            return True
        self._closing = True
        self._restore_cursor()
        threading.Thread(target=self._shutdown, name="shutdown-worker", daemon=False).start()
        return True

    def _shutdown(self) -> None:
        self._gpio.close()
        if self._scheduler:
            self._scheduler.stop()
        if self._switch_thread and self._switch_thread.is_alive():
            self._switch_thread.join()
        self._sessions.stop()
        GLib.idle_add(Gtk.main_quit)
