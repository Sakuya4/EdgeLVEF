# EdgeLVEF

PLAX-only research software for lightweight wall-motion analysis and
experimental low-LVEF screening on edge hardware.

> Research use only. This repository is not a medical device and must not be
> used to diagnose or treat patients.

## Current interpretable LVEF candidate

M1-LVEF3 is the current PLAX-only development candidate:

- role-invariant ShuffleNetV2 LVID tracker, 978,214 parameters;
- FP32 ONNX, approximately 3.85 MiB;
- explicit ED/ES, LVIDd, LVIDs and `LVIDs/LVIDd` outputs;
- three-parameter monotonic LVEF calibration;
- nested development MAE 5.24 percentage points and low-EF F1 0.643.

Run it with:

```bash
python scripts/run_m1_lvef3.py path/to/plax_cine.mp4 --fps 50
```

See [M1-LVEF3 model card](docs/models/m1-lvef3.md). Its calibration has not
been confirmed on an untouched external PLAX cohort.

## Previous wall-motion deployment candidate

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

## Validate an EchoXFlow or strong-label dataset

On the workstation that owns the D:\ or E:\ dataset, prepare
test_config.json from test_config.example.json or answer the two path prompts,
then run:

~~~powershell
python test.py
~~~

The runner performs resume-safe M1-LVEF3 inference when needed, evaluates at
exam level, audits patient/exam fold leakage and subgroup bias, and produces a
de-identified ZIP that can be returned for analysis. Original videos are not
copied. See
[dataset validation instructions](docs/verification/lvef-dataset-validation.md).
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
- [M1-LVEF3 model card](docs/models/m1-lvef3.md)

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
