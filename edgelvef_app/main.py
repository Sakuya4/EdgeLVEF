#!/usr/bin/env python3
"""EdgeLVEF GTK3 application entry point."""

from __future__ import annotations

import sys
import shutil

import config


def cli_available() -> bool:
    if not config.ANALYZE_COMMAND:
        return False
    command = config.ANALYZE_COMMAND[0]
    return shutil.which(command) is not None


def log_startup(Gtk) -> None:
    print("EdgeLVEF GUI starting", flush=True)
    print(f"Python version: {sys.version.split()[0]}", flush=True)
    print(f"GTK version: {Gtk.MAJOR_VERSION}.{Gtk.MINOR_VERSION}.{Gtk.MICRO_VERSION}", flush=True)
    try:
        import cv2

        opencv_version = cv2.__version__
    except ImportError:
        opencv_version = "not available"
    print(f"OpenCV version: {opencv_version}", flush=True)
    print(f"Source mode: {config.SOURCE_MODE}", flush=True)
    print(f"Test video path: {config.TEST_VIDEO_PATH}", flush=True)
    executable = config.ANALYZE_COMMAND[0] if config.ANALYZE_COMMAND else "(not configured)"
    availability = "available" if cli_available() else "not available"
    print(f"EdgeLVEF CLI availability: {availability} ({executable})", flush=True)


def main() -> int:
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk
    except (ImportError, ValueError) as exc:
        print(
            "GTK3/PyGObject is required. On the FRDM image verify: "
            "python3 -c \"import gi; gi.require_version('Gtk','3.0')\"",
            file=sys.stderr,
        )
        print(f"Details: {exc}", file=sys.stderr)
        return 2

    log_startup(Gtk)
    from ui.main_window import MainWindow

    window = MainWindow()
    window.start()
    window.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
