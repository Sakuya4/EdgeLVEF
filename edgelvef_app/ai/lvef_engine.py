"""EdgeLVEF CLI adapter, executed only from the AI worker.

The EdgeLVEF repository was not available at implementation time. Consequently,
this module deliberately does not fabricate an internal Python API. It invokes
the one confirmed entry point (`edgelvef-analyze`) without a shell and accepts
JSON or human-readable key/value output. Replace only this adapter once the
repository's real application service can be inspected.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

import numpy as np

from .result import AnalysisResult
from .engine_base import AnalysisEngine


class EdgeLVEFEngine:
    """Backend-neutral engine used by the GUI.

    Pass a real Python API adapter as ``backend`` when its repository is
    available. The default remains the existing CLI fallback.
    """

    def __init__(
        self,
        command: List[str],
        timeout_seconds: float,
        provider: str,
        backend: Optional[AnalysisEngine] = None,
    ) -> None:
        self.backend: AnalysisEngine = backend or CLIAnalysisBackend(
            command, timeout_seconds, provider
        )

    def analyze(self, frames: Iterable[np.ndarray], fps: float) -> AnalysisResult:
        return self.backend.analyze(frames, fps)

    @staticmethod
    def encode_video(path: Path, frames: List[np.ndarray], fps: float) -> None:
        CLIAnalysisBackend.encode_video(path, frames, fps)

    # Preserve the original parser surface for existing tests and callers.
    @classmethod
    def _parse_output(cls, output: str) -> Dict[str, Any]:
        return CLIAnalysisBackend._parse_output(output)

    @classmethod
    def _result_from_payload(cls, stamp: str, payload: Dict[str, Any]) -> AnalysisResult:
        return CLIAnalysisBackend._result_from_payload(stamp, payload)


class PythonAPIBackend:
    """Injection point for a repository-verified Python application service.

    No EdgeLVEF import, service name, or calling convention is guessed here.
    Supply a callable after inspecting the actual repository. It must accept
    ``(frames, fps)`` and return ``AnalysisResult``.
    """

    def __init__(self, analyze_callable: Callable[[Iterable[np.ndarray], float], AnalysisResult]):
        self._analyze_callable = analyze_callable

    def analyze(self, frames: Iterable[np.ndarray], fps: float) -> AnalysisResult:
        return self._analyze_callable(frames, fps)


class CLIAnalysisBackend:
    """Temporary MP4 + edgelvef-analyze fallback; never used on GTK thread."""

    def __init__(self, command: List[str], timeout_seconds: float, provider: str) -> None:
        self.command = list(command)
        self.timeout_seconds = timeout_seconds
        self.provider = provider

    def analyze(self, frames: Iterable[np.ndarray], fps: float) -> AnalysisResult:
        stamp = datetime.now(timezone.utc).isoformat()
        owned = [np.ascontiguousarray(frame) for frame in frames]
        if len(owned) < 2:
            return AnalysisResult(stamp, False, error="Not enough frames for a cine analysis")
        try:
            if not self.command or shutil.which(self.command[0]) is None:
                raise FileNotFoundError(self.command[0] if self.command else "edgelvef-analyze")
            with tempfile.TemporaryDirectory(prefix="edgelvef-gui-") as temp_dir:
                video_path = Path(temp_dir) / "analysis_window.mp4"
                self.encode_video(video_path, owned, fps)
                command = [token.replace("{video}", str(video_path)) for token in self.command]
                if not any("{video}" in token for token in self.command):
                    command.append(str(video_path))
                completed = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    shell=False,
                )
                output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
                if completed.returncode != 0:
                    detail = output.strip()[-1200:] or f"exit code {completed.returncode}"
                    raise RuntimeError(f"EdgeLVEF analysis failed: {detail}")
                payload = self._parse_output(output)
                return self._result_from_payload(stamp, payload)
        except FileNotFoundError as exc:
            executable = self.command[0] if self.command else "edgelvef-analyze"
            return AnalysisResult(stamp, False, error=f"EdgeLVEF CLI not available: {executable} ({exc})")
        except Exception as exc:
            return AnalysisResult(stamp, False, error=str(exc))

    @staticmethod
    def encode_video(path: Path, frames: List[np.ndarray], fps: float) -> None:
        import cv2

        height, width = frames[0].shape[:2]
        writer = cv2.VideoWriter(
            str(path), cv2.VideoWriter_fourcc(*"mp4v"), max(float(fps), 1.0), (width, height)
        )
        if not writer.isOpened():
            raise RuntimeError("OpenCV could not create the temporary MP4 cine")
        try:
            for frame in frames:
                if frame.shape[:2] != (height, width):
                    frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
                if frame.ndim == 2:
                    frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                writer.write(frame)
        finally:
            writer.release()
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError("Temporary cine encoding produced an empty file")

    @classmethod
    def _parse_output(cls, output: str) -> Dict[str, Any]:
        text = output.strip()
        # Prefer a complete JSON document; otherwise accept the last JSON object line.
        candidates = [text] + [line.strip() for line in reversed(text.splitlines())]
        for candidate in candidates:
            if not candidate.startswith("{"):
                continue
            try:
                value = json.loads(candidate)
                if isinstance(value, dict):
                    return value
            except json.JSONDecodeError:
                continue

        payload: Dict[str, Any] = {}
        patterns = {
            "lvef": r"(?i)\b(?:lvef|ef)\b\s*[:=]\s*(-?\d+(?:\.\d+)?)",
            "global_fs": r"(?i)\b(?:global[ _-]?fs|fs)\b\s*[:=]\s*(-?\d+(?:\.\d+)?)",
            "confidence": r"(?i)\b(?:wall[ _-]?confidence|confidence)\b\s*[:=]\s*(-?\d+(?:\.\d+)?)",
            "valid_frame_fraction": r"(?i)\bvalid[ _-]?frame[ _-]?fraction\b\s*[:=]\s*(-?\d+(?:\.\d+)?)",
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, text)
            if match:
                payload[key] = float(match.group(1))
        if "lvef" not in payload:
            raise ValueError("EdgeLVEF output contained no parseable LVEF value")
        return payload

    @staticmethod
    def _number(payload: Dict[str, Any], *keys: str) -> Optional[float]:
        lowered = {str(k).lower(): v for k, v in payload.items()}
        for key in keys:
            value = lowered.get(key.lower())
            if value is not None:
                return float(value)
        return None

    @classmethod
    def _result_from_payload(cls, stamp: str, payload: Dict[str, Any]) -> AnalysisResult:
        lvef = cls._number(payload, "lvef", "ef", "ejection_fraction")
        if lvef is None or not 0 <= lvef <= 100:
            raise ValueError(f"Invalid LVEF result: {lvef!r}")
        return AnalysisResult(
            timestamp=stamp,
            success=True,
            lvef=lvef,
            global_fs=cls._number(payload, "global_fs", "globalFS", "fs"),
            confidence=cls._number(payload, "wall_confidence", "confidence"),
            valid_frame_fraction=cls._number(payload, "valid_frame_fraction"),
            ed_frame=int(cls._number(payload, "ed", "ed_frame")) if cls._number(payload, "ed", "ed_frame") is not None else None,
            es_frame=int(cls._number(payload, "es", "es_frame")) if cls._number(payload, "es", "es_frame") is not None else None,
            low_ef_score=cls._number(payload, "low_ef_score"),
            raw=payload,
        )
