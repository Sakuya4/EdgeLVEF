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

### Interfaces

CLI modules parse operator input and serialize results. They contain no model
math. `scripts/` contains only thin launchers around these interfaces.

## Frozen artifact rule

Board validation must use the files under `models/student_model/` without
editing them. Any retraining, threshold selection, quantization, or graph
conversion creates a new model version and requires a new model card, checksum,
and validation report.
