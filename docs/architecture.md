# Clean Architecture

The repository keeps physiology rules independent from runtimes and user
interfaces. Dependencies point inward.

```text
interfaces/cli
    -> application/analyze_cine
        -> domain/wall_tracking + domain/lvef
        -> application/ports.WallProbabilityModel
    -> infrastructure adapters

infrastructure/onnx_wall_model
    implements WallProbabilityModel

interfaces/scripts/run_m1_lvef3
    -> application/analyze_lvid_cine
        -> domain/interpretable_lvef
        -> application/ports.LvidTrajectoryModel
    -> infrastructure/onnx_lvid_tracker + calibration_config
```

## Layer responsibilities

### Domain

`domain/wall_tracking.py` contains only NumPy geometry:

- two-wall centerline extraction;
- temporal trajectory smoothing;
- ED/ES candidate selection;
- global and regional fractional shortening.

`domain/lvef.py` contains the frozen mapping and low-EF decision rule. It does
not import OpenCV, ONNX Runtime, PyTorch, or operating-system APIs.

`domain/interpretable_lvef.py` contains the three-parameter monotonic mapping
from measured LVIDd/LVIDs to the M1-LVEF3 development estimate. It exposes the
raw ratio and applicability-range check.

### Application

`application/analyze_cine.py` coordinates one analysis. It accepts a
`WallProbabilityModel` port, extracts wall features, and applies the frozen
head. The application layer does not know whether inference runs on CPU, GPU,
or an NPU provider.

### Infrastructure

- `onnx_wall_model.py`: preprocessing and ONNX Runtime adapter.
- `video.py`: MP4/AVI/MOV/MKV/NPZ decoding.
- `head_config.py`: JSON configuration adapter.
- `benchmark.py`: target-system and latency measurements.
- `onnx_lvid_tracker.py`: role-invariant LVID endpoint and trajectory adapter.
- `calibration_config.py`: frozen M1-LVEF3 parameter loader.

### Interfaces

CLI modules parse operator input and serialize results. They contain no model
math. `scripts/` contains only thin launchers around these interfaces.

## Frozen artifact rule

Board validation must use the files under `models/student_model/` without
editing them. Any retraining, threshold selection, quantization, or graph
conversion creates a new model version and requires a new model card, checksum,
and validation report.
