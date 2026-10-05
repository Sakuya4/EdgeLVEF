# Reproduction and packaging boundary

Run from `research/plax_lvef`. Public tests use synthetic inputs only:

```sh
python -m pip install -r requirements.txt
python -m pytest tests -q
python scripts/train_teacher.py --help
python scripts/train_student.py --help
python scripts/run_m10_motion_fusion.py --help
python scripts/run_m11_motion_diagnostic.py --help
```

Environment used for local experiments:Windows,Anaconda Python,CUDA GPU.
CPU tests/CLI are verified at publishing time; target-Linux full training and
i.MX93 performance are not verified by these packaging checks. Requirements
are minimum ranges,not an exact frozen environment or deterministic guarantee.

## Authorized inputs

Teacher manifest columns:subject_id,study_id,file_id,dicom_path,EF_value,split.
Cache index columns:subject_id,study_id,file_id,path,lvef,split.
Each local NPZ contains `frames` as uint8[T,112,112]. Only PLAX-selected cines
belong here. Access/selection of MIMIC and label linkage must be reproduced
by an authorized researcher; no manifest records are redistributed.
Subject IDs must belong to only one split; study EF must be consistent across
cines. Teacher-target NPZ stores aligned `prediction` and512-D `embedding`.
Credentialed identifiers/caches/targets/checkpoints/predictions stay in a protected
local derived directory. Local exception messages may contain paths; redact
before sharing terminal logs. Public aggregate summaries must be inspected
before external release.

## Main Teacher and Student

`train_teacher.py --variant gao` reproduces the published-style R(2+1)D
regression. Original Teacher seeds20261001/20261002,64 frames,stride2,
112px,validation selection. Effective batch16/32 must be realized via batch
and accumulation settings from the original protocol; do not silently replace
them with defaults and call the result exact replication.

`train_student.py --backbone mobilenet_v3_large` is the selected Student;
the default remains Small for legacy compatibility,so explicitly set Large.
Original Student:seed20261001,max30 epochs,patience7,batch8,32 frames,
best epoch18 (25 epochs completed). Teacher caches/checkpoints are local inputs.
See script `--help` for required paths; do not train using invented labels.

## M10 / M11 diagnostics

Public exports retain scientific code and replace the workstation-specific
protected-root literal with REQUIRED `--credentialed-root` for portability.
The locator adapter contains the exact checkpoint loader and soft-coordinate
extraction,not a checkpoint. M1 locator weights are separately required for
M10 and are not redistributed. M11 reuses the complete M10 map cache.

Example M11 command with authorized local paths supplied by the operator:

```sh
python scripts/run_m11_motion_diagnostic.py \
  --credentialed-root /protected/derived \
  --cache-index /protected/derived/cache_112/restricted_index.csv \
  --teacher-cache /protected/derived/teacher_targets.npz \
  --motion-cache /protected/derived/m10/cache \
  --secure-output /protected/derived/m11 \
  --summary-output /local/aggregate-results/m11 \
  --epochs 20 --seed 20261005
```

Do not reuse an original Windows run folder with the public-export script
hash:strict run-signature checks intentionally reject changed implementations.
Choose a new protected reproduction output. Tiny `--smoke` runs test execution,
not model quality. Histories/checkpoints are selected on validation before test
metrics. Existing development test has been repeatedly inspected; do not label
it as untouched validation in a paper.

M9 aggregate results are included,but its full original multi-dataset training
pipeline is not exported in this bundle. Do not claim end-to-end M9 reproduction
from this package. This package is not an App integration or model-weight update.
