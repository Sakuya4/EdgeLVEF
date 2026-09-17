from __future__ import annotations

import json
from pathlib import Path

from ..domain.interpretable_lvef import MonotonicLvefCalibration


def load_monotonic_calibration(path: Path) -> MonotonicLvefCalibration:
    values = json.loads(path.read_text(encoding="utf-8"))
    parameters = values["parameters"]
    applicability = values["applicability"]
    return MonotonicLvefCalibration(
        intercept=float(parameters["intercept"]),
        scale=float(parameters["scale"]),
        exponent=float(parameters["exponent"]),
        low_ef_definition=float(values["low_ef_definition_percent"]),
        ratio_min=float(applicability["lvid_ratio_p01"]),
        ratio_max=float(applicability["lvid_ratio_p99"]),
    )
