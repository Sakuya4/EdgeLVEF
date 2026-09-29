"""Runtime configuration for the FRDM i.MX93 EdgeLVEF GUI."""

from __future__ import annotations

import os
import shlex
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def project_path(value: str) -> Path:
    """Resolve relative deployment paths against main.py, not process cwd."""
    path = Path(value).expanduser()
    return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()

SOURCE_MODE = os.getenv("EDGELVEF_SOURCE_MODE", "video").strip().lower()
TEST_VIDEO_PATH = project_path(os.getenv("EDGELVEF_TEST_VIDEO", "test_data/plax.avi"))

BUFFER_SECONDS = float(os.getenv("EDGELVEF_BUFFER_SECONDS", "5"))
ANALYSIS_INTERVAL_SECONDS = float(os.getenv("EDGELVEF_ANALYSIS_INTERVAL", "3"))
SMOOTHING_WINDOW = int(os.getenv("EDGELVEF_SMOOTHING_WINDOW", "3"))
FALLBACK_FPS = float(os.getenv("EDGELVEF_FALLBACK_FPS", "30"))
ONNX_PROVIDER = os.getenv("EDGELVEF_ONNX_PROVIDER", "CPUExecutionProvider")

# The repository was not present while this app was built, so no internal API is
# invented here. This template calls the repository's known CLI in an isolated
# worker. Override it if `edgelvef-analyze --help` on the target shows a different
# video-input form. Every token is passed directly (never through a shell).
ANALYZE_COMMAND = shlex.split(
    os.getenv("EDGELVEF_ANALYZE_COMMAND", "edgelvef-analyze {video}")
)
ANALYSIS_TIMEOUT_SECONDS = float(os.getenv("EDGELVEF_ANALYSIS_TIMEOUT", "180"))

SAVED_DIR = project_path(os.getenv("EDGELVEF_SAVED_DIR", "saved"))
WINDOW_WIDTH = 480
WINDOW_HEIGHT = 320

# Board-specific GPIO mapping is intentionally unset until the actual header
# line is verified. Example chip value later: "/dev/gpiochip0".
RESET_BUTTON_GPIO_CHIP = os.getenv("EDGELVEF_RESET_GPIO_CHIP", "")
RESET_BUTTON_GPIO_LINE = int(os.getenv("EDGELVEF_RESET_GPIO_LINE", "-1"))
RESET_BUTTON_DEBOUNCE_SECONDS = float(os.getenv("EDGELVEF_RESET_DEBOUNCE", "0.25"))
