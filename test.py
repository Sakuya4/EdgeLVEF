from __future__ import annotations

import argparse
import csv
import hashlib
import json
import secrets
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PREDICTION_FIELDS = ("pred_lvef", "predicted_lvef", "lvef_percent")
SHARE_FIELDS = (
    "patient_code", "exam_code", "recording_code", "fold", "label_source",
    "site", "vendor", "sex", "age_group", "recording_count", "gt_lvef",
    "gt_source", "pred_lvef", "low_ef_probability", "signed_error",
    "absolute_error", "true_low_ef", "predicted_low_ef", "classification",
    "lvidd_px", "lvids_px", "lvid_ratio", "ed_frame", "es_frame",
    "median_endpoint_confidence", "inside_development_ratio_range",
    "input_frames", "fps_used", "model_sha256", "model_name", "status",
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="One-command EdgeLVEF dataset inference, evaluation, and shareable ZIP"
    )
    parser.add_argument("--config", type=Path, default=ROOT / "test_config.json")
    parser.add_argument("--non-interactive", action="store_true")
    return parser.parse_args()


def _prompt_config(config_path: Path, non_interactive: bool) -> dict[str, object]:
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    if non_interactive:
        raise FileNotFoundError(f"Config does not exist: {config_path}")
    print("No test_config.json was found. Enter the dataset-workstation paths.")
    manifest = input("Manifest CSV path (for example D:\\EchoXFlow\\strong_manifest.csv): ").strip().strip('"')
    if not manifest:
        raise ValueError("Manifest path is required")
    default_output = "E:\\EdgeLVEF_results" if Path("E:/").exists() else str(ROOT / "outputs" / "dataset_validation")
    output = input(f"Output directory [{default_output}]: ").strip().strip('"') or default_output
    return {
        "manifest": manifest,
        "output_root": output,
        "provider": "CPUExecutionProvider",
        "default_fps": 50.0,
        "bootstrap": 2000,
        "require_patient_id": True,
        "group_columns": ["label_source", "site", "vendor", "sex", "age_group"],
        "run_inference": "auto",
    }


def _read_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            return [item.strip() for item in next(reader)]
        except StopIteration as exc:
            raise ValueError("Manifest is empty") from exc


def _run(command: list[str], log_handle) -> None:
    printable = subprocess.list2cmdline(command)
    print(f"\n> {printable}")
    log_handle.write(f"\n> {printable}\n")
    log_handle.flush()
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="")
        log_handle.write(line)
    code = process.wait()
    log_handle.flush()
    if code:
        raise RuntimeError(f"Command failed with exit code {code}: {printable}")


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "unknown"


def _code(prefix: str, value: str, salt: str) -> str:
    if not value:
        return ""
    digest = hashlib.sha256(f"{salt}:{value}".encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _deidentify_predictions(source: Path, destination: Path, salt: str) -> dict[str, int]:
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    shared = []
    counts = {"rows": len(rows), "tp": 0, "fn": 0, "tn": 0, "fp": 0, "failed": 0}
    for row in rows:
        item = {
            "patient_code": _code("patient", row.get("patient_id", ""), salt),
            "exam_code": _code("exam", row.get("exam_id", ""), salt),
            "recording_code": _code("recording", row.get("recording_id", ""), salt),
        }
        item.update({field: row.get(field, "") for field in SHARE_FIELDS if field not in item})
        classification = row.get("classification", "").lower()
        if classification in counts:
            counts[classification] += 1
        if row.get("status", "ok") != "ok":
            counts["failed"] += 1
        shared.append(item)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(SHARE_FIELDS))
        writer.writeheader()
        writer.writerows(shared)
    return counts


def _shareable_zip(run_dir: Path, source_manifest: Path, config: dict[str, object]) -> Path:
    evaluation = run_dir / "evaluation"
    share = run_dir / "shareable"
    share.mkdir(exist_ok=True)
    for name in ("report.md", "group_metrics.csv", "threshold_sweep.csv"):
        shutil.copy2(evaluation / name, share / name)

    metrics = json.loads((evaluation / "metrics.json").read_text(encoding="utf-8"))
    metrics["manifest"] = source_manifest.name
    (share / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    salt = secrets.token_hex(16)
    counts = _deidentify_predictions(
        evaluation / "exam_predictions.csv",
        share / "exam_predictions_deidentified.csv",
        salt,
    )
    metadata = {
        "schema_version": 1,
        "created_at_local": datetime.now().astimezone().isoformat(),
        "git_commit": _git_commit(),
        "python": sys.version,
        "source_manifest_filename": source_manifest.name,
        "identifiers": "SHA-256 pseudonyms with a run-only salt; original paths and IDs excluded",
        "counts": counts,
        "settings": {
            "bootstrap": int(config.get("bootstrap", 2000)),
            "require_patient_id": bool(config.get("require_patient_id", True)),
            "group_columns": config.get("group_columns", []),
        },
    }
    (share / "run_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    zip_path = run_dir.parent / f"{run_dir.name}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(share.iterdir()):
            archive.write(file, file.name)
    return zip_path


def main() -> None:
    args = _arguments()
    config = _prompt_config(args.config, args.non_interactive)
    manifest = Path(str(config["manifest"])).expanduser()
    if not manifest.is_absolute():
        manifest = (ROOT / manifest).resolve()
    if not manifest.is_file():
        raise FileNotFoundError(f"Manifest does not exist: {manifest}")

    output_root = Path(str(config.get("output_root", ROOT / "outputs" / "dataset_validation"))).expanduser()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_root / f"EdgeLVEF_validation_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "resolved_config.local.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    header = _read_header(manifest)
    prediction_manifest = run_dir / "m1_lvef3_predictions.csv"
    run_setting = config.get("run_inference", "auto")
    run_inference = not any(field in header for field in PREDICTION_FIELDS)
    if isinstance(run_setting, bool):
        run_inference = run_setting

    log_path = run_dir / "test.log"
    try:
        with log_path.open("w", encoding="utf-8") as log:
            if run_inference:
                if "video_path" not in header:
                    raise ValueError("Inference requested but manifest has no video_path column")
                command = [
                    sys.executable, "-m", "edgelvef.interfaces.cli.batch_lvef3",
                    str(manifest), "--output", str(prediction_manifest),
                    "--provider", str(config.get("provider", "CPUExecutionProvider")),
                    "--default-fps", str(config.get("default_fps", 50.0)),
                ]
                if config.get("crop"):
                    command += ["--crop", str(config["crop"])]
                _run(command, log)
                evaluation_input = prediction_manifest
            else:
                print("Prediction column detected; inference is skipped.")
                log.write("Prediction column detected; inference is skipped.\n")
                evaluation_input = manifest

            evaluation_dir = run_dir / "evaluation"
            command = [
                sys.executable, "-m", "edgelvef.interfaces.cli.evaluate_lvef",
                str(evaluation_input), "--output-dir", str(evaluation_dir),
                "--bootstrap", str(config.get("bootstrap", 2000)),
                "--seed", str(config.get("seed", 20260917)),
                "--low-ef-definition", str(config.get("low_ef_definition", 40.0)),
                "--alert-ef-threshold", str(config.get("alert_ef_threshold", 40.0)),
                "--probability-threshold", str(config.get("probability_threshold", 0.5)),
                "--group-columns", ",".join(config.get("group_columns", [])),
            ]
            if config.get("require_patient_id", True):
                command.append("--require-patient-id")
            _run(command, log)
        zip_path = _shareable_zip(run_dir, evaluation_input, config)
    except Exception:
        print(f"\nFAILED. Local log retained at: {log_path}")
        raise

    print("\nVALIDATION COMPLETE")
    print(f"Local full results: {run_dir}")
    print(f"ZIP READY TO RETURN: {zip_path}")
    print("The ZIP excludes original video paths and replaces patient/exam/recording IDs with pseudonyms.")


if __name__ == "__main__":
    main()
