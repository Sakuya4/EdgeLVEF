import csv
import json

import pytest

from edgelvef.evaluation.lvef_dataset import evaluate_manifest


def _write(path, rows):
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_evaluator_aggregates_recordings_and_computes_low_ef_metrics(tmp_path):
    rows = [
        {"patient_id": "p1", "exam_id": "e1", "recording_id": "r1a", "fold": "0", "gt_lvef": "30", "pred_lvef": "30", "site": "A"},
        {"patient_id": "p1", "exam_id": "e1", "recording_id": "r1b", "fold": "0", "gt_lvef": "30", "pred_lvef": "34", "site": "A"},
        {"patient_id": "p2", "exam_id": "e2", "recording_id": "r2", "fold": "1", "gt_lvef": "35", "pred_lvef": "44", "site": "A"},
        {"patient_id": "p3", "exam_id": "e3", "recording_id": "r3", "fold": "2", "gt_lvef": "45", "pred_lvef": "43", "site": "B"},
        {"patient_id": "p4", "exam_id": "e4", "recording_id": "r4", "fold": "3", "gt_lvef": "55", "pred_lvef": "60", "site": "B"},
        {"patient_id": "p5", "exam_id": "e5", "recording_id": "r5", "fold": "4", "gt_lvef": "65", "pred_lvef": "58", "site": "B"},
        {"patient_id": "p6", "exam_id": "e6", "recording_id": "r6", "fold": "0", "gt_lvef": "50", "pred_lvef": "49", "site": "B"},
    ]
    manifest = tmp_path / "predictions.csv"
    _write(manifest, rows)
    result = evaluate_manifest(manifest, tmp_path / "report", group_columns=["site"], bootstrap_repetitions=50)
    metrics = result["metrics"]
    assert result["audit"]["aggregated_exams"] == 6
    assert metrics["mae"] == pytest.approx(26 / 6)
    assert metrics["bias"] == pytest.approx(1.0)
    assert (metrics["tp"], metrics["fn"], metrics["tn"], metrics["fp"]) == (1, 1, 4, 0)
    assert metrics["sensitivity"] == pytest.approx(0.5)
    assert metrics["specificity"] == pytest.approx(1.0)
    assert result["bootstrap"]["metadata"]["group_unit"] == "patient_id"
    for name in ("metrics.json", "report.md", "exam_predictions.csv", "group_metrics.csv", "threshold_sweep.csv"):
        assert (tmp_path / "report" / name).exists()
    saved = json.loads((tmp_path / "report" / "metrics.json").read_text(encoding="utf-8"))
    assert saved["metrics"]["positive_n"] == 2


def test_evaluator_derives_reference_from_edv_esv(tmp_path):
    rows = [
        {"patient_id": "p1", "exam_id": "e1", "recording_id": "r1", "fold": "0", "gt_lvef": "", "edv": "100", "esv": "60", "pred_lvef": "42"},
        {"patient_id": "p2", "exam_id": "e2", "recording_id": "r2", "fold": "1", "gt_lvef": "60", "edv": "", "esv": "", "pred_lvef": "58"},
    ]
    manifest = tmp_path / "derived.csv"
    _write(manifest, rows)
    result = evaluate_manifest(manifest, tmp_path / "report", bootstrap_repetitions=0)
    assert result["metrics"]["mae"] == pytest.approx(2.0)
    assert result["metrics"]["positive_n"] == 1


def test_evaluator_rejects_patient_fold_leakage(tmp_path):
    rows = [
        {"patient_id": "same", "exam_id": "e1", "recording_id": "r1", "fold": "0", "gt_lvef": "35", "pred_lvef": "34"},
        {"patient_id": "same", "exam_id": "e2", "recording_id": "r2", "fold": "1", "gt_lvef": "55", "pred_lvef": "54"},
    ]
    manifest = tmp_path / "leak.csv"
    _write(manifest, rows)
    with pytest.raises(ValueError, match="patient fold leakage"):
        evaluate_manifest(manifest, tmp_path / "report", bootstrap_repetitions=0)
