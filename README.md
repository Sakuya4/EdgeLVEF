# EdgeLVEF

PLAX-only research software for lightweight wall-motion analysis and
experimental low-LVEF screening on edge hardware.

> Research use only. This repository is not a medical device and must not be
> used to diagnose or treat patients.

## Current deployment candidate

The primary deployment path is the **Student Model**:

- MobileNetV3-Small two-wall heatmap model
- 985,634 parameters
- FP32 ONNX, 3.77 MiB
- 320 x 320 frames, dynamic batch
- SHA-256 `FE5FC82...3956194`
- full-cycle global fractional shortening mapped by a frozen development-only
  linear head

The older Student v4 direct-regression ensemble remains under
`checkpoints/student_v4/` for reproducibility, but it is not the recommended
board-validation target.

## Install

```bash
git clone https://github.com/Sakuya4/EdgeLVEF.git
cd EdgeLVEF
python -m pip install -e .
```

## Analyze one PLAX cine

Use a PLAX-compatible cine containing at least one full cardiac cycle:

```bash
edgelvef-analyze path/to/plax_cine.mp4 --provider CPUExecutionProvider
```

The input must show the scan-converted ultrasound sector, not the complete
machine user interface. Crop a full-interface export before analysis:

```bash
edgelvef-analyze cine.mp4 --crop 120,40,920,840
```

The output includes the experimental LVEF mapping, low-EF score, global
fractional shortening, wall confidence, valid-frame fraction, and ED/ES phase.
The LVEF output is secondary research output; it is not a clinical measurement.

Render the predicted walls and ED/ES candidates for visual verification:

```bash
edgelvef-render path/to/plax_cine.mp4 outputs/wall-overlay.mp4
```

## Validate an Embedded Linux board

Run on the physical board, not on the development computer:

```bash
bash scripts/run_embedded_verification.sh imx93-board CPUExecutionProvider
```

The JSON result records the model checksum, operating system, architecture,
active ONNX provider, median/p95 latency, output shape, and finite-output check.
Do not label CPU fallback as NPU execution.

Detailed instructions:

- [Architecture](docs/architecture.md)
- [Embedded Linux verification](docs/verification/embedded-linux.md)
- [Acceptance criteria](docs/verification/acceptance-criteria.md)
- [Result template](docs/verification/report-template.md)
- [Validation roadmap](docs/verification/validation-roadmap.md)
- [Student Model card](docs/models/student-model.md)

## Repository boundaries

```text
edgelvef/domain          Pure wall geometry and frozen decision rules
edgelvef/application     Cine-analysis use cases and ports
edgelvef/infrastructure ONNX Runtime, video, configuration, system adapters
edgelvef/interfaces      Command-line entry points
models/                  Frozen deployable artifacts and checksums
scripts/                 Thin operator scripts; no model logic
tests/                   Unit and ONNX integration tests
docs/                    Architecture and verification procedures
checkpoints/student_v4   Legacy research baseline
```

## Evidence boundary

The current confirmatory EchoXFlow evaluation used 68 exams, only five of which
had LVEF <=40%. Raw global fractional shortening achieved AUROC 0.902; the
continuous mapping had MAE 6.57 percentage points and overestimated the low-EF
tail. These are internal research results, not external clinical validation.

No patient images or source training data are included.
