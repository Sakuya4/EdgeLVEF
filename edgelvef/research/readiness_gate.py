"""Architecture of the fixed thesis R1 MobileNetV3-Small readiness artifact."""
from __future__ import annotations

import torch
from torch import nn
from torchvision import models


class ReadinessGateModel(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        backbone = models.mobilenet_v3_small(weights=None)
        self.features = backbone.features
        self.pool = nn.AdaptiveAvgPool2d((1, 1))
        self.shared = nn.Sequential(
            nn.Dropout(.25), nn.Linear(backbone.classifier[0].in_features, 256),
            nn.Hardswish(), nn.Dropout(.20),
        )
        self.view_head = nn.Linear(256, 2)
        self.readiness_head = nn.Linear(256, 4)
        self.quality_head = nn.Linear(256, 5)

    def encode(self, clips: torch.Tensor) -> torch.Tensor:
        batch, window, channels, height, width = clips.shape
        features = self.pool(self.features(clips.reshape(batch*window, channels, height, width))).flatten(1)
        return self.shared(features.reshape(batch, window, -1).mean(1))

    def forward(self, clips: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        shared = self.encode(clips)
        return self.view_head(shared), self.readiness_head(shared), self.quality_head(shared)
