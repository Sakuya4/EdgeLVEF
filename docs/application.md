# EdgeLVEF application guide

The application repository includes a Linux instrument interface, video-analysis commands, input assessment and i.MX93 acquisition integration. The research package provides the selected Teacher and Student definitions; runtime commands load their configured artifacts.

## Installation

```bash
git clone https://github.com/Sakuya4/EdgeLVEF.git
cd EdgeLVEF
python -m pip install -e .
```

For model architecture and training dependencies, use [research/plax_lvef/requirements.txt](../research/plax_lvef/requirements.txt).

## PLAX input assessment

```bash
edgelvef-readiness path/to/plax_cine.mp4
```

The output contains view, readiness and quality probabilities. To analyze only the ultrasound sector from a full-interface export, provide the crop coordinates:

```bash
edgelvef-readiness path/to/plax_cine.mp4 --crop 120,40,920,840
```

## Existing measurement commands

The video-regression architecture is described in the [research package](../research/plax_lvef/). The following operator commands use the repository's configured wall or LVID measurement artifacts:

```bash
edgelvef-analyze path/to/plax_cine.mp4 --provider CPUExecutionProvider
edgelvef-render path/to/plax_cine.mp4 outputs/wall-overlay.mp4
python scripts/run_m1_lvef3.py path/to/plax_cine.mp4 --fps 50
```

These produce measurement summaries and overlays. Input should contain the scan-converted PLAX sector. Apply `--crop` where supported to remove machine-interface borders.

## Linux instrument interface

[edgelvef_app](../edgelvef_app/) contains the GTK interface, measurement-session logic and service configuration. Its operator README specifies the display environment, launch script and reset control.

The [P42 acquisition package](../hardware/aco-p42-imx93-headless-sidecar/) contains the board-local Android SDK adapter and Linux image transport. Use its deployment procedures with a legally obtained SDK and a device license stored outside Git.

## Board and dataset evaluation

```bash
bash scripts/run_embedded_verification.sh imx93-board CPUExecutionProvider
```

The report records the configured model checksum, active execution provider, latency and output checks. [Embedded Linux verification](verification/embedded-linux.md) defines the report fields.

On an authorized dataset workstation, [test.py](../test.py) provides exam-level measurement evaluation and a shareable aggregate report. See [dataset evaluation](verification/lvef-dataset-validation.md) for input and export settings.
