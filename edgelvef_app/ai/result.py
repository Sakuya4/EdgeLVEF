"""UI-neutral analysis result."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class AnalysisResult:
    timestamp: str
    success: bool
    lvef: Optional[float] = None
    global_fs: Optional[float] = None
    confidence: Optional[float] = None
    valid_frame_fraction: Optional[float] = None
    ed_frame: Optional[int] = None
    es_frame: Optional[int] = None
    low_ef_score: Optional[float] = None
    error: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

