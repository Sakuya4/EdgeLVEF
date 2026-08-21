# Embedded Linux verification

This procedure is for the person holding the physical board.

## 1. Record the immutable revision

```bash
git rev-parse HEAD
sha256sum -c models/student_model/SHA256SUMS
```

Both checksums must pass before testing. Do not convert or quantize the model
during this verification.

## 2. Install and run repository tests

Python 3.10 or newer is required.

```bash
python -m pip install -e .
python -m pip install pytest
python -m pytest -q
```

Record any skipped test and its reason. A missing ONNX provider is a failed
deployment configuration, not a model accuracy result.

## 3. Run the physical-board benchmark

CPU baseline:

```bash
bash scripts/run_embedded_verification.sh imx93-board CPUExecutionProvider
```

This creates `outputs/imx93-board-benchmark.json`. Check that:

- `physical_target_claimed` is `true`;
- `system` is `Linux`;
- `checksum_passed` is `true`;
- `providers_active` contains the requested provider;
- output shape is `[1, 2, 320, 320]`;
- `finite_outputs` is `true`.

If an NPU provider is available, rerun with its exact provider name. The result
is an NPU result only when `providers_active` confirms it. Do not infer NPU use
from the board model or theoretical TOPS.

## 4. Functional cine test

Use a de-identified PLAX cine containing a complete cardiac cycle. The model
expects the scan-converted ultrasound sector. Use `--crop x1,y1,x2,y2` if the
export includes the complete machine interface:

```bash
edgelvef-analyze path/to/deidentified_plax.mp4 --provider CPUExecutionProvider \
  > outputs/functional-cine.json
```

Verify that the program returns finite values and does not raise
`Fewer than 60% of cycle frames have both wall paths`. That exception is a
model/quality failure and must remain in the denominator.

Render the same cine for visual inspection:

```bash
edgelvef-render path/to/deidentified_plax.mp4 outputs/wall-overlay.mp4 \
  --provider CPUExecutionProvider
```

The reviewer should verify that the white and gray paths remain on opposing LV
endocardial walls through most of the cycle, and that ED/ES candidates coincide
with visually plausible maximum/minimum cavity dimensions. Record failures;
do not change the model or threshold from this inspection.

Do not send patient cine files to the public repository. Return only JSON,
software versions, and a written description of the test source.

## 5. Return package

Return these files to the model team:

- benchmark JSON;
- functional-cine JSON;
- wall-overlay MP4 or a written visual rating; do not return patient media when
  data governance prohibits transfer;
- `git rev-parse HEAD`;
- `python --version` and `python -m pip freeze`;
- board name, RAM, storage, power mode, and cooling method;
- whether execution was CPU or a confirmed NPU provider.
