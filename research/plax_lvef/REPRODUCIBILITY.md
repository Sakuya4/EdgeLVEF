# Training and architecture reproduction

Run from `research/plax_lvef`:

```bash
python -m pip install -r requirements.txt
python -m pytest tests -q
python scripts/train_teacher.py --help
python scripts/train_student.py --help
```

## Input records

Teacher manifest columns are `subject_id, study_id, file_id, dicom_path, EF_value, split`. The decoded cache index uses `subject_id, study_id, file_id, path, lvef, split`. Each cine cache contains a uint8 `frames` array with shape `[T,112,112]`.

Select PLAX cines and keep each patient in one partition. All cines in a study share the study EF reference. Image files, manifests, Teacher targets, checkpoints and individual predictions are stored in an authorized local data directory.

## Teacher training

```bash
python scripts/train_teacher.py \
  --manifest /protected/derived/plax_manifest.csv \
  --cache-root /protected/derived/cache_112 \
  --secure-output /protected/derived/teacher_batch16 \
  --summary-output /local/aggregate/teacher_batch16 \
  --frames 64 --stride 2 --image-size 112 \
  --batch-size 4 --accumulate 4 --seed 20261001
```

Train the second Teacher with seed 20261002 and the recorded effective batch size 32. The ensemble averages EF predictions and 512-D representations.

## Student training

```bash
python scripts/train_student.py \
  --cache-index /protected/derived/cache_112/restricted_index.csv \
  --teacher-checkpoint /protected/derived/teacher_batch16/best.pt \
  --teacher-checkpoint /protected/derived/teacher_batch32/best.pt \
  --teacher-cache /protected/derived/teacher_targets.npz \
  --secure-output /protected/derived/student \
  --summary-output /local/aggregate/student \
  --backbone mobilenet_v3_large \
  --frames 32 --image-size 112 --batch-size 8 \
  --epochs 30 --patience 7 --seed 20261001
```

The script checks Teacher-target alignment, trains with the specified distillation objective and selects the checkpoint using validation MAE. It then aggregates evaluation cines to study-level predictions.

## Architecture checks

The tests instantiate networks with `pretrained=False` and verify output shapes and parameter counts. The selected Student count is 3,212,755. The two Teachers total 62,601,276 parameters.

Training is separate from the device runtime. Device evaluation records model checksums, provider selection, numerical agreement, latency, memory and power through the [verification procedures](../../docs/verification/embedded-linux.md).

## Data handling

Use your own authorized dataset access. Keep restricted inputs and individual outputs in the protected data directory. Publish aggregate results after privacy review. This package does not distribute trained LVEF weights or patient records.
