"""Optional libgpiod v1 reset-button adapter with graceful failure."""

from __future__ import annotations

import importlib
import threading
import time
from typing import Callable


def is_reset_key(key_name: str) -> bool:
    return isinstance(key_name, str) and key_name.lower() == "r"


def dispatch_reset_key(key_name: str, on_reset: Callable[[], None]) -> bool:
    if not is_reset_key(key_name):
        return False
    on_reset()
    return True


class GPIOResetButton:
    def __init__(self, chip: str, line: int, on_reset: Callable[[], None], debounce_seconds=0.25):
        self.chip_name = chip
        self.line_number = line
        self.on_reset = on_reset
        self.debounce_seconds = debounce_seconds
        self._chip = None
        self._line = None
        self._thread = None
        self._stop = threading.Event()

    def start(self) -> bool:
        if not self.chip_name or self.line_number < 0:
            print("Warning: GPIO reset button is not configured; keyboard R remains available", flush=True)
            return False
        try:
            gpiod = importlib.import_module("gpiod")
            self._chip = gpiod.Chip(self.chip_name)
            self._line = self._chip.get_line(self.line_number)
            kwargs = {"consumer": "edgelvef-reset", "type": gpiod.LINE_REQ_EV_FALLING_EDGE}
            bias = getattr(gpiod, "LINE_REQ_FLAG_BIAS_PULL_UP", None)
            if bias is not None:
                kwargs["flags"] = bias
            self._line.request(**kwargs)
            self._thread = threading.Thread(target=self._run, name="gpio-reset", daemon=False)
            self._thread.start()
            print(f"GPIO reset enabled: {self.chip_name} line {self.line_number}", flush=True)
            return True
        except Exception as exc:
            print(f"Warning: GPIO reset unavailable: {exc}; keyboard R remains available", flush=True)
            self.close()
            return False

    def _run(self) -> None:
        last_event = float("-inf")
        while not self._stop.is_set():
            try:
                if not self._line.event_wait(sec=0.2):
                    continue
                self._line.event_read()
                now = time.monotonic()
                if now - last_event >= self.debounce_seconds:
                    last_event = now
                    self.on_reset()
            except Exception as exc:
                if not self._stop.is_set():
                    print(f"Warning: GPIO reset listener stopped: {exc}", flush=True)
                return

    def close(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.0)
        if self._line is not None:
            try:
                self._line.release()
            except Exception:
                pass
            self._line = None
        if self._chip is not None:
            try:
                self._chip.close()
            except Exception:
                pass
            self._chip = None
