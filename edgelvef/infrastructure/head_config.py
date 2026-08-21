from __future__ import annotations

import json
from pathlib import Path

from ..domain.lvef import FrozenEdgeHead


def load_frozen_head(path: Path) -> FrozenEdgeHead:
    values = json.loads(path.read_text(encoding="utf-8"))
    return FrozenEdgeHead(
        intercept=float(values["lvef_intercept"]),
        global_fs_slope=float(values["lvef_global_fs_slope"]),
        low_ef_score_threshold=float(values["low_ef_score_threshold"]),
        low_ef_definition=float(values["low_ef_definition"]),
    )
