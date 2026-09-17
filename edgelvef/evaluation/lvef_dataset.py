from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

GT_FIELDS = ("gt_lvef", "lvef", "reference_lvef")
PRED_FIELDS = ("pred_lvef", "predicted_lvef", "lvef_percent")
PROB_FIELDS = ("low_ef_probability", "pred_low_ef_probability")


def _value(row: dict[str, str], fields: tuple[str, ...]) -> float | None:
    for field in fields:
        text = row.get(field, "").strip()
        if text:
            value = float(text)
            if not math.isfinite(value):
                raise ValueError(f"{field} is not finite")
            return value
    return None


def _ground_truth(row: dict[str, str]) -> tuple[float | None, str]:
    value = _value(row, GT_FIELDS)
    if value is not None:
        if not 0 <= value <= 100:
            raise ValueError(f"GT LVEF outside [0,100]: {value}")
        return value, "manifest_lvef"
    edv, esv = _value(row, ("edv",)), _value(row, ("esv",))
    if edv is None and esv is None:
        return None, "missing"
    if edv is None or esv is None or edv <= 0 or esv < 0 or esv > edv:
        raise ValueError(f"invalid EDV/ESV: {edv}/{esv}")
    return 100 * (edv - esv) / edv, "derived_from_edv_esv"


def load_manifest(path: Path) -> tuple[list[dict[str, object]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        raw = list(reader)
    if not raw:
        raise ValueError("manifest has no data rows")
    rows: list[dict[str, object]] = []
    for line, source in enumerate(raw, 2):
        try:
            exam_id = source.get("exam_id", "").strip()
            if not exam_id:
                raise ValueError("exam_id is required")
            gt, gt_source = _ground_truth(source)
            pred = _value(source, PRED_FIELDS)
            prob = _value(source, PROB_FIELDS)
            if pred is not None and not 0 <= pred <= 100:
                raise ValueError(f"predicted LVEF outside [0,100]: {pred}")
            if prob is not None and not 0 <= prob <= 1:
                raise ValueError(f"low-EF probability outside [0,1]: {prob}")
        except ValueError as exc:
            raise ValueError(f"row {line}: {exc}") from exc
        rows.append({
            **{k: (v or "").strip() for k, v in source.items() if k is not None},
            "exam_id": exam_id,
            "patient_id": source.get("patient_id", "").strip(),
            "recording_id": source.get("recording_id", "").strip(),
            "fold": source.get("fold", "").strip(),
            "gt_lvef": gt,
            "gt_source": gt_source,
            "pred_lvef": pred,
            "low_ef_probability": prob,
        })
    warnings = []
    missing_gt = sum(row["gt_lvef"] is None for row in rows)
    missing_pred = sum(row["pred_lvef"] is None for row in rows)
    if missing_gt:
        warnings.append(f"{missing_gt} recording rows lack strong GT and are excluded from accuracy metrics.")
    if missing_pred:
        warnings.append(f"{missing_pred} recording rows lack predictions and are excluded from paired metrics.")
    return rows, warnings


def audit_splits(rows: list[dict[str, object]], require_patient_id: bool) -> dict[str, object]:
    exam_folds: dict[str, set[str]] = defaultdict(set)
    patient_folds: dict[str, set[str]] = defaultdict(set)
    missing = 0
    for row in rows:
        fold = str(row["fold"])
        patient = str(row["patient_id"])
        if fold:
            exam_folds[str(row["exam_id"])].add(fold)
        if patient and fold:
            patient_folds[patient].add(fold)
        if not patient:
            missing += 1
    leaking_exams = sorted(k for k, v in exam_folds.items() if len(v) > 1)
    leaking_patients = sorted(k for k, v in patient_folds.items() if len(v) > 1)
    if leaking_exams:
        raise ValueError(f"exam fold leakage: {leaking_exams[:10]}")
    if leaking_patients:
        raise ValueError(f"patient fold leakage: {leaking_patients[:10]}")
    if require_patient_id and missing:
        raise ValueError(f"patient_id missing from {missing} rows")
    return {
        "exam_fold_leakage": False,
        "patient_fold_leakage": False,
        "rows_missing_patient_id": missing,
    }


def aggregate_exams(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["exam_id"])].append(row)
    exams = []
    for exam_id, items in sorted(grouped.items()):
        gt = [float(x["gt_lvef"]) for x in items if x["gt_lvef"] is not None]
        pred = [float(x["pred_lvef"]) for x in items if x["pred_lvef"] is not None]
        prob = [float(x["low_ef_probability"]) for x in items if x["low_ef_probability"] is not None]
        if gt and np.ptp(gt) > 1e-6:
            raise ValueError(f"inconsistent GT within exam {exam_id}: {gt}")
        for field in ("patient_id", "fold"):
            values = {str(x[field]) for x in items if str(x[field])}
            if len(values) > 1:
                raise ValueError(f"inconsistent {field} within exam {exam_id}")
        item = dict(items[0])
        item.update({
            "recording_count": len(items),
            "gt_lvef": gt[0] if gt else None,
            "pred_lvef": float(np.median(pred)) if pred else None,
            "low_ef_probability": float(np.median(prob)) if prob else None,
            "exam_aggregation": "median",
        })
        exams.append(item)
    return exams


def _div(a: float, b: float) -> float | None:
    return a / b if b else None


def _auc(labels: np.ndarray, scores: np.ndarray) -> float | None:
    pos = int(labels.sum())
    neg = len(labels) - pos
    if not pos or not neg:
        return None
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores), dtype=float)
    start = 0
    while start < len(scores):
        end = start + 1
        while end < len(scores) and scores[order[end]] == scores[order[start]]:
            end += 1
        ranks[order[start:end]] = (start + 1 + end) / 2
        start = end
    return float((ranks[labels].sum() - pos * (pos + 1) / 2) / (pos * neg))


def _ap(labels: np.ndarray, scores: np.ndarray) -> float | None:
    pos = int(labels.sum())
    if not pos:
        return None
    order = np.argsort(-scores, kind="mergesort")
    labels, scores = labels[order], scores[order]
    tp = fp = start = 0
    previous_recall = area = 0.0
    while start < len(labels):
        end = start + 1
        while end < len(labels) and scores[end] == scores[start]:
            end += 1
        found = int(labels[start:end].sum())
        tp += found
        fp += end - start - found
        recall = tp / pos
        area += (recall - previous_recall) * tp / (tp + fp)
        previous_recall, start = recall, end
    return float(area)


def compute_metrics(rows: list[dict[str, object]], low: float, alert: float, probability_cutoff: float) -> dict[str, object]:
    paired = [r for r in rows if r["gt_lvef"] is not None and r["pred_lvef"] is not None]
    if not paired:
        raise ValueError("no rows contain both strong GT and predicted LVEF")
    gt = np.asarray([r["gt_lvef"] for r in paired], dtype=float)
    pred = np.asarray([r["pred_lvef"] for r in paired], dtype=float)
    error = pred - gt
    true_low = gt <= low
    probabilities_complete = all(r["low_ef_probability"] is not None for r in paired)
    if probabilities_complete:
        score = np.asarray([r["low_ef_probability"] for r in paired], dtype=float)
        predicted_low = score >= probability_cutoff
        score_source = "low_ef_probability"
    else:
        score = -pred
        predicted_low = pred <= alert
        score_source = "negative_predicted_lvef"
    tp = int(np.sum(predicted_low & true_low))
    fn = int(np.sum(~predicted_low & true_low))
    tn = int(np.sum(~predicted_low & ~true_low))
    fp = int(np.sum(predicted_low & ~true_low))
    sensitivity, specificity = _div(tp, tp + fn), _div(tn, tn + fp)
    pearson = None if len(gt) < 2 or np.std(gt) == 0 or np.std(pred) == 0 else float(np.corrcoef(gt, pred)[0, 1])
    mean_gt, mean_pred = float(gt.mean()), float(pred.mean())
    var_gt, var_pred = float(np.var(gt)), float(np.var(pred))
    covariance = float(np.mean((gt - mean_gt) * (pred - mean_pred)))
    ccc_den = var_gt + var_pred + (mean_gt - mean_pred) ** 2
    tss = float(np.sum((gt - mean_gt) ** 2))
    sd = float(np.std(error, ddof=1)) if len(error) > 1 else None
    return {
        "n": len(paired), "positive_n": int(true_low.sum()), "negative_n": int((~true_low).sum()),
        "prevalence": float(true_low.mean()), "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error ** 2))), "bias": float(error.mean()),
        "pearson_r": pearson, "r2": 1 - float(np.sum(error ** 2)) / tss if tss else None,
        "ccc": 2 * covariance / ccc_den if ccc_den else None,
        "bland_altman_lower": float(error.mean() - 1.96 * sd) if sd is not None else None,
        "bland_altman_upper": float(error.mean() + 1.96 * sd) if sd is not None else None,
        "within_5_points": float(np.mean(np.abs(error) <= 5)),
        "within_10_points": float(np.mean(np.abs(error) <= 10)),
        "low_ef_definition": low, "alert_ef_threshold": alert,
        "probability_threshold": probability_cutoff if probabilities_complete else None,
        "classification_score_source": score_source,
        "tp": tp, "fn": fn, "tn": tn, "fp": fp,
        "accuracy": _div(tp + tn, len(gt)), "sensitivity": sensitivity, "specificity": specificity,
        "balanced_accuracy": None if sensitivity is None or specificity is None else (sensitivity + specificity) / 2,
        "ppv": _div(tp, tp + fp), "npv": _div(tn, tn + fn), "f1": _div(2 * tp, 2 * tp + fp + fn),
        "auroc": _auc(true_low, score), "auprc": _ap(true_low, score),
    }


def annotate(rows: list[dict[str, object]], low: float, alert: float, probability_cutoff: float) -> list[dict[str, object]]:
    result = []
    for source in rows:
        row = dict(source)
        gt, pred, prob = row["gt_lvef"], row["pred_lvef"], row["low_ef_probability"]
        if gt is not None and pred is not None:
            true_low = float(gt) <= low
            predicted_low = float(prob) >= probability_cutoff if prob is not None else float(pred) <= alert
            row.update({
                "signed_error": float(pred) - float(gt), "absolute_error": abs(float(pred) - float(gt)),
                "true_low_ef": true_low, "predicted_low_ef": predicted_low,
                "classification": ("TP" if true_low else "FP") if predicted_low else ("FN" if true_low else "TN"),
            })
        result.append(row)
    return result


def subgroup_metrics(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    groups = (
        ("<=40", lambda x: x <= 40), ("40-50", lambda x: 40 < x < 50),
        ("50-60", lambda x: 50 <= x < 60), (">=60", lambda x: x >= 60),
    )
    output = []
    for name, condition in groups:
        selected = [r for r in rows if r["gt_lvef"] is not None and r["pred_lvef"] is not None and condition(float(r["gt_lvef"]))]
        errors = np.asarray([float(r["pred_lvef"]) - float(r["gt_lvef"]) for r in selected])
        output.append({
            "subgroup": name, "n": len(selected),
            "mae": float(np.mean(np.abs(errors))) if len(errors) else None,
            "mean_reference": float(np.mean([r["gt_lvef"] for r in selected])) if selected else None,
            "mean_prediction": float(np.mean([r["pred_lvef"] for r in selected])) if selected else None,
            "bias": float(np.mean(errors)) if len(errors) else None,
        })
    return output


def grouped_metrics(rows: list[dict[str, object]], columns: list[str], low: float, alert: float, probability_cutoff: float) -> list[dict[str, object]]:
    output = []
    for column in columns:
        values: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in rows:
            values[str(row.get(column, "")).strip() or "<missing>"].append(row)
        for value, selected in sorted(values.items()):
            try:
                metrics = compute_metrics(selected, low, alert, probability_cutoff)
            except ValueError:
                continue
            output.append({"group_column": column, "group_value": value, **metrics})
    return output


def threshold_sweep(rows: list[dict[str, object]], low: float) -> list[dict[str, object]]:
    paired = [r for r in rows if r["gt_lvef"] is not None and r["pred_lvef"] is not None]
    gt = np.asarray([r["gt_lvef"] for r in paired], dtype=float)
    pred = np.asarray([r["pred_lvef"] for r in paired], dtype=float)
    true_low = gt <= low
    output = []
    for threshold in np.unique(np.concatenate(([0.0], pred, [100.0]))):
        positive = pred <= threshold
        tp, fn = int(np.sum(positive & true_low)), int(np.sum(~positive & true_low))
        tn, fp = int(np.sum(~positive & ~true_low)), int(np.sum(positive & ~true_low))
        sensitivity, specificity = _div(tp, tp + fn), _div(tn, tn + fp)
        output.append({
            "alert_ef_threshold": float(threshold), "tp": tp, "fn": fn, "tn": tn, "fp": fp,
            "sensitivity": sensitivity, "specificity": specificity,
            "balanced_accuracy": None if sensitivity is None or specificity is None else (sensitivity + specificity) / 2,
        })
    return output


def bootstrap(rows: list[dict[str, object]], low: float, alert: float, probability_cutoff: float, repetitions: int, seed: int) -> dict[str, object]:
    if repetitions <= 0:
        return {}
    group_key = "patient_id" if all(str(r.get("patient_id", "")) for r in rows) else "exam_id"
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        groups[str(row[group_key])].append(row)
    keys = sorted(groups)
    rng = np.random.default_rng(seed)
    samples: dict[str, list[float]] = defaultdict(list)
    names = ("mae", "rmse", "bias", "sensitivity", "specificity", "balanced_accuracy", "auroc", "auprc")
    for _ in range(repetitions):
        chosen = rng.choice(keys, len(keys), replace=True)
        sample = [row for key in chosen for row in groups[str(key)]]
        values = compute_metrics(sample, low, alert, probability_cutoff)
        for name in names:
            value = values[name]
            if value is not None and math.isfinite(float(value)):
                samples[name].append(float(value))
    result: dict[str, object] = {"metadata": {"group_unit": group_key, "requested_repetitions": repetitions}}
    for name, values in samples.items():
        result[name] = {
            "lower_95": float(np.quantile(values, 0.025)), "upper_95": float(np.quantile(values, 0.975)),
            "valid_repetitions": len(values),
        }
    return result


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        fields.extend(key for key in row if key not in fields)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _fmt(value: object) -> str:
    return "NA" if value is None else f"{value:.4f}" if isinstance(value, float) else str(value)


def _markdown(result: dict[str, object]) -> str:
    metrics = result["metrics"]
    audit = result["audit"]
    subgroups = result["ef_subgroups"]
    assert isinstance(metrics, dict) and isinstance(audit, dict) and isinstance(subgroups, list)
    lines = [
        "# LVEF dataset validation report", "",
        "> Research evaluation only. GT is the supplied research reference, not absolute clinical truth.", "",
        "## Cohort audit", "",
        f"- Manifest rows: {audit['manifest_rows']}", f"- Aggregated exams: {audit['aggregated_exams']}",
        f"- Paired exams: {metrics['n']}", f"- Low-EF exams: {metrics['positive_n']} ({_fmt(metrics['prevalence'])})",
        f"- Bootstrap unit: {result['bootstrap'].get('metadata', {}).get('group_unit', 'disabled')}", "",
        "## Continuous LVEF", "", "| Metric | Result |", "|---|---:|",
    ]
    for name in ("mae", "rmse", "bias", "pearson_r", "r2", "ccc", "bland_altman_lower", "bland_altman_upper", "within_5_points", "within_10_points"):
        lines.append(f"| {name} | {_fmt(metrics[name])} |")
    lines += ["", "## Low EF", "", "| Metric | Result |", "|---|---:|"]
    for name in ("tp", "fn", "tn", "fp", "sensitivity", "specificity", "balanced_accuracy", "ppv", "npv", "f1", "auroc", "auprc"):
        lines.append(f"| {name} | {_fmt(metrics[name])} |")
    lines += ["", "## EF subgroups", "", "| GT subgroup | N | MAE | Mean prediction | Bias |", "|---|---:|---:|---:|---:|"]
    for row in subgroups:
        lines.append(f"| {row['subgroup']} | {row['n']} | {_fmt(row['mae'])} | {_fmt(row['mean_prediction'])} | {_fmt(row['bias'])} |")
    lines += ["", "## Warnings", ""]
    warnings = result.get("warnings", [])
    lines += [f"- {warning}" for warning in warnings] if warnings else ["- None"]
    lines += [
        "", "## Guardrails", "",
        "- A threshold sweep on the evaluation cohort is exploratory, not confirmatory.",
        "- Small subgroup differences are hypotheses until independently validated.",
        "- Pseudo labels and teacher predictions must not be counted as GT.", "",
    ]
    return "\n".join(lines)


def evaluate_manifest(
    manifest: Path,
    output_dir: Path,
    low_ef_definition: float = 40.0,
    alert_ef_threshold: float = 40.0,
    probability_threshold: float = 0.5,
    group_columns: list[str] | None = None,
    bootstrap_repetitions: int = 2000,
    seed: int = 20260917,
    require_patient_id: bool = False,
) -> dict[str, object]:
    rows, warnings = load_manifest(manifest)
    split_audit = audit_splits(rows, require_patient_id)
    exams = aggregate_exams(rows)
    paired = [r for r in exams if r["gt_lvef"] is not None and r["pred_lvef"] is not None]
    metrics = compute_metrics(paired, low_ef_definition, alert_ef_threshold, probability_threshold)
    if metrics["positive_n"] < 20:
        warnings.append("Fewer than 20 low-EF exams: sensitivity and AUPRC are highly uncertain.")
    if split_audit["rows_missing_patient_id"]:
        warnings.append("patient_id is incomplete; bootstrap falls back to exam level and cannot exclude patient leakage.")
    if metrics["classification_score_source"] == "negative_predicted_lvef":
        warnings.append("No complete low-EF probability; AUROC/AUPRC use negative predicted LVEF as the score.")
    annotated = annotate(exams, low_ef_definition, alert_ef_threshold, probability_threshold)
    boot = bootstrap(paired, low_ef_definition, alert_ef_threshold, probability_threshold, bootstrap_repetitions, seed)
    result: dict[str, object] = {
        "schema_version": 1, "manifest": str(manifest.resolve()),
        "audit": {"manifest_rows": len(rows), "aggregated_exams": len(exams), "paired_exams": len(paired), **split_audit},
        "metrics": metrics, "bootstrap": boot, "ef_subgroups": subgroup_metrics(paired), "warnings": warnings,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metrics.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / "report.md").write_text(_markdown(result), encoding="utf-8")
    _write_csv(output_dir / "exam_predictions.csv", annotated)
    _write_csv(output_dir / "group_metrics.csv", grouped_metrics(
        paired, group_columns or [], low_ef_definition, alert_ef_threshold, probability_threshold
    ))
    _write_csv(output_dir / "threshold_sweep.csv", threshold_sweep(paired, low_ef_definition))
    return result
