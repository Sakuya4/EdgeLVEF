from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from ..domain.wall_tracking import centerline_from_heatmap, cycle_wall_features


def render_wall_overlay(
    grayscale_frames: np.ndarray,
    probabilities: np.ndarray,
    output_path: Path,
    fps: float = 15.0,
) -> dict[str, float | int | str]:
    if len(grayscale_frames) != len(probabilities):
        raise ValueError("Frame and probability counts differ")
    features = cycle_wall_features(probabilities)
    ed = round(features["ed_phase_fraction"] * max(1, len(grayscale_frames) - 1))
    es = round(features["es_phase_fraction"] * max(1, len(grayscale_frames) - 1))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (320, 320))
    if not writer.isOpened():
        raise RuntimeError(f"Cannot open video writer: {output_path}")
    try:
        for frame_index, (frame, heatmaps) in enumerate(zip(grayscale_frames, probabilities)):
            canvas = cv2.cvtColor(cv2.resize(frame, (320, 320)), cv2.COLOR_GRAY2BGR)
            for channel, color in ((0, (255, 255, 255)), (1, (160, 160, 160))):
                try:
                    path, _ = centerline_from_heatmap(heatmaps[channel])
                    points = np.round(path[:, ::-1]).astype(np.int32)
                    cv2.polylines(canvas, [points], False, color, 2, cv2.LINE_AA)
                except ValueError:
                    continue
            if frame_index == ed:
                cv2.putText(canvas, "ED candidate", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, .55, (255, 255, 255), 1)
            if frame_index == es:
                cv2.putText(canvas, "ES candidate", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, .55, (255, 255, 255), 1)
            writer.write(canvas)
    finally:
        writer.release()
    return {
        "output": str(output_path),
        "frames": len(grayscale_frames),
        "global_fractional_shortening": features["global_fs"],
        "valid_frame_fraction": features["valid_frame_fraction"],
        "mean_wall_confidence": features["mean_wall_confidence"],
        "ed_frame": ed,
        "es_frame": es,
    }
