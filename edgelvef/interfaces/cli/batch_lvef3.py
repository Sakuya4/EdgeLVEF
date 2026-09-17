from __future__ import annotations

import argparse
import csv
from pathlib import Path

from ...application.analyze_lvid_cine import analyze_lvid_cine
from ...infrastructure.calibration_config import load_monotonic_calibration
from ...infrastructure.onnx_lvid_tracker import OnnxLvidTracker
from ...infrastructure.video import crop_frames, load_grayscale_cine
from .analyze import REPOSITORY_ROOT

MODEL_SHA256 = "CC95301A37A131F3926EA85A2FAB7A86DDED13C5DD2501F21FEEAB4D213C6B42"


def _crop(text: str) -> tuple[int, int, int, int] | None:
    if not text.strip():
        return None
    values = tuple(int(x) for x in text.split(","))
    if len(values) != 4:
        raise ValueError("crop must be x1,y1,x2,y2")
    return values


def _read(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("manifest has no data rows")
    for line, row in enumerate(rows, 2):
        if not row.get("exam_id", "").strip() or not row.get("video_path", "").strip():
            raise ValueError(f"row {line}: exam_id and video_path are required")
    return rows


def _write_atomic(path: Path, rows: list[dict[str, object]]) -> None:
    fields: list[str] = []
    for row in rows:
        fields.extend(key for key in row if key not in fields)
    temporary = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Resume-safe M1-LVEF3 inference over a video manifest")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=REPOSITORY_ROOT / "models/m1_lvef3/m1_lvid_tracker_fp32.onnx")
    parser.add_argument("--calibration", type=Path, default=REPOSITORY_ROOT / "models/m1_lvef3/balanced_calibration.json")
    parser.add_argument("--provider", default="CPUExecutionProvider")
    parser.add_argument("--default-fps", type=float, default=50.0)
    parser.add_argument("--crop", default="")
    parser.add_argument("--rerun-success", action="store_true")
    args = parser.parse_args()

    inputs = _read(args.manifest)
    existing: dict[str, dict[str, str]] = {}
    if args.output.exists():
        with args.output.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                key = row.get("recording_id", "") or row.get("exam_id", "")
                if key:
                    existing[key] = row

    tracker = OnnxLvidTracker(args.model, args.provider, MODEL_SHA256)
    calibration = load_monotonic_calibration(args.calibration)
    output: list[dict[str, object]] = []
    for index, source in enumerate(inputs, 1):
        key = source.get("recording_id", "").strip() or source["exam_id"].strip()
        if not args.rerun_success and key in existing and existing[key].get("status") == "ok":
            output.append(existing[key])
            continue
        row: dict[str, object] = dict(source)
        video = Path(source["video_path"].strip())
        if not video.is_absolute():
            video = (args.manifest.parent / video).resolve()
        try:
            fps = float(source.get("fps", "").strip() or args.default_fps)
            crop = _crop(source.get("crop", "").strip() or args.crop)
            frames = crop_frames(load_grayscale_cine(video), crop)
            result = analyze_lvid_cine(frames, fps, tracker, calibration).to_dict()
            row.update({
                "video_path": str(video), "pred_lvef": result["lvef_percent"],
                "predicted_low_ef": result["predicts_lvef_at_or_below_40"],
                "lvidd_px": result["lvidd_px"], "lvids_px": result["lvids_px"],
                "lvid_ratio": result["lvid_ratio"], "ed_frame": result["ed_frame"],
                "es_frame": result["es_frame"], "median_endpoint_confidence": result["median_endpoint_confidence"],
                "inside_development_ratio_range": result["inside_development_ratio_range"],
                "input_frames": result["input_frames"], "fps_used": fps,
                "model_sha256": MODEL_SHA256, "model_name": "M1-LVEF3",
                "status": "ok", "error": "",
            })
            print(f"[{index}/{len(inputs)}] OK {key}")
        except Exception as exc:
            row.update({"video_path": str(video), "status": "error", "error": f"{type(exc).__name__}: {exc}"})
            print(f"[{index}/{len(inputs)}] ERROR {key}: {exc}")
        output.append(row)
        _write_atomic(args.output, output)
    failures = sum(row.get("status") != "ok" for row in output)
    print(f"complete: {len(output) - failures} succeeded, {failures} failed; {args.output}")


if __name__ == "__main__":
    main()
