from __future__ import annotations

import torch
from torch import nn
from torchvision import models


class TemporalResidualBlock(nn.Module):
    def __init__(self, channels: int, dilation: int):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv1d(
                channels,
                channels,
                kernel_size=3,
                padding=dilation,
                dilation=dilation,
                groups=channels,
                bias=False,
            ),
            nn.Conv1d(channels, channels, kernel_size=1, bias=False),
            nn.GroupNorm(8, channels),
            nn.Hardswish(),
            nn.Dropout(0.1),
        )

    def forward(self, sequence: torch.Tensor) -> torch.Tensor:
        return sequence + self.block(sequence)


def _mobilenet_v3_small() -> tuple[nn.Module, int]:
    network = models.mobilenet_v3_small(weights=None)
    first = network.features[0][0]
    network.features[0][0] = nn.Conv2d(
        1,
        first.out_channels,
        kernel_size=first.kernel_size,
        stride=first.stride,
        padding=first.padding,
        bias=False,
    )
    return network.features, 576


class EdgeLvefModel(nn.Module):
    def __init__(self, label_mean: float, label_std: float):
        super().__init__()
        self.encoder, feature_dim = _mobilenet_v3_small()
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.volume_head = nn.Linear(feature_dim, 1)
        self.frame_projection = nn.Sequential(
            nn.Linear(feature_dim, 128),
            nn.Hardswish(),
        )
        self.temporal_blocks = nn.Sequential(
            TemporalResidualBlock(128, dilation=1),
            TemporalResidualBlock(128, dilation=2),
            TemporalResidualBlock(128, dilation=4),
        )
        self.temporal_head = nn.Sequential(
            nn.Linear(256, 128),
            nn.Hardswish(),
            nn.Dropout(0.2),
            nn.Linear(128, 1),
        )
        self.low_ef_head = nn.Sequential(
            nn.Linear(256, 128),
            nn.Hardswish(),
            nn.Dropout(0.2),
            nn.Linear(128, 1),
        )
        self.register_buffer("label_mean", torch.tensor(float(label_mean)))
        self.register_buffer("label_std", torch.tensor(float(label_std)))

    def forward(self, frames: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        batch, time, channels, height, width = frames.shape
        encoded = self.encoder(frames.reshape(batch * time, channels, height, width))
        features = self.pool(encoded).flatten(1).reshape(batch, time, -1)
        sequence = self.frame_projection(features).transpose(1, 2)
        sequence = self.temporal_blocks(sequence)
        temporal = torch.cat([sequence.mean(dim=2), sequence.amax(dim=2)], dim=1)
        normalized_lvef = self.temporal_head(temporal).squeeze(1)
        lvef = normalized_lvef * self.label_std + self.label_mean
        low_ef_probability = torch.sigmoid(self.low_ef_head(temporal).squeeze(1))
        return lvef, low_ef_probability
