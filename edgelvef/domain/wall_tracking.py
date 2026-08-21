from __future__ import annotations

import numpy as np


REGIONS = ("apical", "mid", "basal")


def centerline_from_heatmap(
    heatmap: np.ndarray,
    n_points: int = 24,
    threshold: float = 0.30,
) -> tuple[np.ndarray, float]:
    coordinates = np.argwhere(heatmap >= threshold).astype(np.float32)
    if len(coordinates) < n_points:
        raise ValueError("Insufficient foreground for a wall centerline")
    weights = heatmap[coordinates[:, 0].astype(int), coordinates[:, 1].astype(int)].astype(np.float32)
    center = np.average(coordinates, axis=0, weights=weights)
    centered = coordinates - center
    covariance = (centered * weights[:, None]).T @ centered / weights.sum()
    _, eigenvectors = np.linalg.eigh(covariance)
    projection = centered @ eigenvectors[:, -1]
    groups = np.array_split(np.argsort(projection), n_points)
    path = np.stack([np.average(coordinates[group], axis=0, weights=weights[group]) for group in groups])
    return path, float(weights.mean())


def aligned_distance_profile(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    direct = np.linalg.norm(first[0] - second[0]) + np.linalg.norm(first[-1] - second[-1])
    reverse = np.linalg.norm(first[0] - second[-1]) + np.linalg.norm(first[-1] - second[0])
    if reverse < direct:
        second = second[::-1]
    distances = np.linalg.norm(first - second, axis=1)
    return distances[::-1] if distances[0] > distances[-1] else distances


def _temporal_median(values: np.ndarray, width: int = 5) -> np.ndarray:
    radius = width // 2
    padded = np.pad(values, ((radius, radius), (0, 0)), mode="edge")
    return np.stack([np.median(padded[index:index + width], axis=0) for index in range(len(values))])


def cycle_wall_features(probabilities: np.ndarray) -> dict[str, float]:
    if probabilities.ndim != 4 or probabilities.shape[1] != 2:
        raise ValueError("Expected probabilities shaped [frames, 2, height, width]")
    profiles = []
    confidence = []
    for frame in probabilities:
        try:
            first, first_confidence = centerline_from_heatmap(frame[0])
            second, second_confidence = centerline_from_heatmap(frame[1])
            profiles.append(aligned_distance_profile(first, second))
            confidence.append(min(first_confidence, second_confidence))
        except ValueError:
            profiles.append(np.full(24, np.nan, dtype=np.float32))
            confidence.append(0.0)
    profiles = np.asarray(profiles)
    valid = np.isfinite(profiles).all(axis=1)
    if valid.mean() < 0.60:
        raise ValueError("Fewer than 60% of cycle frames have both wall paths")
    frame_indices = np.arange(len(profiles))
    for point in range(profiles.shape[1]):
        profiles[:, point] = np.interp(frame_indices, frame_indices[valid], profiles[valid, point])
    profiles = _temporal_median(profiles)
    thirds = np.array_split(np.arange(profiles.shape[1]), 3)
    regional = np.stack([profiles[:, indices].mean(axis=1) for indices in thirds], axis=1)
    global_distance = profiles.mean(axis=1)
    ed_stop = max(2, int(np.ceil(0.20 * len(profiles))))
    es_start = max(1, int(np.floor(0.20 * len(profiles))))
    es_stop = max(es_start + 1, int(np.ceil(0.70 * len(profiles))))
    ed_index = int(np.argmax(global_distance[:ed_stop]))
    es_index = int(es_start + np.argmin(global_distance[es_start:es_stop]))
    ed = regional[ed_index]
    es = regional[es_index]
    shortening = np.clip((ed - es) / np.maximum(ed, 1e-6), -1.0, 1.0)
    result = {
        "valid_frame_fraction": float(valid.mean()),
        "mean_wall_confidence": float(np.mean(confidence)),
        "ed_phase_fraction": float(ed_index / max(1, len(profiles) - 1)),
        "es_phase_fraction": float(es_index / max(1, len(profiles) - 1)),
        "global_fs": float((global_distance[ed_index] - global_distance[es_index]) / global_distance[ed_index]),
        "global_ed_distance_norm": float(global_distance[ed_index] / probabilities.shape[-1]),
    }
    for index, name in enumerate(REGIONS):
        result[f"{name}_fs"] = float(shortening[index])
        result[f"{name}_ed_distance_norm"] = float(ed[index] / probabilities.shape[-1])
    return result
