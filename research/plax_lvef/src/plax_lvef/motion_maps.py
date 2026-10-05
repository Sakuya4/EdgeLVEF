"""Synthetic M-mode sampling and conservative diameter-period proposals.

These proposals are not clinical ED/ES labels or calibrated diameters.
"""
import cv2
import numpy as np
import torch
from torch import nn


def median_anchor(points: np.ndarray, valid: np.ndarray) -> tuple[np.ndarray, float]:
    coverage = float(valid.mean())
    fallback = np.array([[56, 28], [56, 80]], dtype=np.float32)
    if coverage < .70:
        return fallback, coverage
    anchor = np.median(points[valid], axis=0)
    length = float(np.linalg.norm(anchor[1] - anchor[0]))
    # Individually valid endpoints do not guarantee a valid coordinate median.
    if not np.isfinite(anchor).all() or not 8 <= length <= 70:
        return fallback, 0.0
    return anchor, coverage


def cycle_window(diameter: np.ndarray) -> tuple[int, int, bool]:
    n = len(diameter)
    if n < 24 or not np.isfinite(diameter).all():
        return 0, n - 1, False
    curve = np.convolve(np.pad(diameter, (2, 2), mode="edge"), np.ones(5) / 5, mode="valid")
    if np.ptp(curve) < 2.0:
        return 0, n - 1, False
    centered = curve - curve.mean()
    # No reliable frame rate in this cache: sample-domain periodicity only.
    lags = np.arange(8, n // 2 + 1)
    scores = np.array([np.corrcoef(centered[:-k], centered[k:])[0, 1] for k in lags])
    local = [i for i in range(1, len(scores) - 1)
             if scores[i] >= scores[i - 1] and scores[i] > scores[i + 1]]
    if not local:
        return 0, n - 1, False
    best = max(local, key=lambda i: scores[i])
    if not np.isfinite(scores[best]) or scores[best] < 0.5:
        return 0, n - 1, False
    lag = int(lags[best])
    peaks = np.flatnonzero((curve[1:-1] > curve[:-2]) & (curve[1:-1] >= curve[2:])) + 1
    pairs = [(int(a), int(b)) for a in peaks for b in peaks
             if a < b and abs((b - a) - lag) <= max(2, round(lag * 0.2))]
    if not pairs:
        return 0, n - 1, False
    a, b = min(pairs, key=lambda pair: abs(pair[1] - pair[0] - lag))
    return a, b, True


def sample_motion_map(cine: np.ndarray, endpoints: np.ndarray,
                      start: int = 0, stop: int | None = None) -> np.ndarray:
    """Five parallel fixed-in-space lines; keep displacement amplitude intact."""
    stop = len(cine) - 1 if stop is None else stop
    a, b = np.asarray(endpoints, dtype=np.float32)
    axis = b - a
    length = float(np.linalg.norm(axis))
    if length < 1 or not np.isfinite(endpoints).all():
        raise ValueError("Degenerate motion-map anchor")
    axis /= length
    normal = np.array([-axis[1], axis[0]])
    center = (a + b) / 2
    # Fixed 80-pixel extent avoids normalizing away chamber-width differences.
    positions = np.linspace(-40, 40, 80, dtype=np.float32)
    times = np.rint(np.linspace(start, stop, 128)).astype(int)
    maps = []
    for offset in (-12, -6, 0, 6, 12):
        xy = center + positions[:, None] * axis + offset * normal
        mx, my = xy[:, 0:1].copy(), xy[:, 1:2].copy()
        maps.append(np.stack([cv2.remap(cine[t], mx, my, cv2.INTER_LINEAR,
                                       borderMode=cv2.BORDER_CONSTANT).ravel() for t in times], axis=1))
    return np.stack(maps).astype(np.uint8)


class MotionFusion(nn.Module):
    """Residual correction of frozen appearance predictions, not EF geometry."""
    def __init__(self, motion: bool):
        super().__init__()
        self.motion = motion
        blocks = []
        for incoming, outgoing in ((5, 16), (16, 32), (32, 64)):
            blocks.extend([nn.Conv2d(incoming, outgoing, 3, stride=2, padding=1),
                           nn.GroupNorm(4, outgoing), nn.Hardswish()])
        self.motion_encoder = nn.Sequential(*blocks, nn.AdaptiveAvgPool2d(1), nn.Flatten())
        self.fusion = nn.Sequential(nn.Linear(320, 128), nn.Hardswish(), nn.Dropout(0.2))
        self.ef = nn.Linear(128, 1)
        self.low = nn.Linear(128, 1)
        self.projector = nn.Linear(320, 512)
        for head in (self.ef, self.low):
            nn.init.zeros_(head.weight)
            nn.init.zeros_(head.bias)
        if not motion:
            self.motion_encoder.requires_grad_(False)

    def forward(self, feature, base_ef, base_low, maps):
        extra = self.motion_encoder(maps) if self.motion else feature.new_zeros((len(feature), 64))
        combined = torch.cat((feature, extra), dim=1)
        hidden = self.fusion(combined)
        return (base_ef + self.ef(hidden).squeeze(1),
                base_low + self.low(hidden).squeeze(1), self.projector(combined))
