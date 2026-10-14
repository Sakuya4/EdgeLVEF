"""Study-level PLAX video models for EF Teacher learning."""

from __future__ import annotations

import torch
from torch import nn
from torchvision.models.video import R2Plus1D_18_Weights, r2plus1d_18


class R2Plus1DEncoder(nn.Module):
    def __init__(self, pretrained: bool = True):
        super().__init__()
        weights = R2Plus1D_18_Weights.KINETICS400_V1 if pretrained else None
        network = r2plus1d_18(weights=weights)
        self.stem = network.stem
        self.layer1 = network.layer1
        self.layer2 = network.layer2
        self.layer3 = network.layer3
        self.layer4 = network.layer4
        self.channels = 512

    def forward(self, clips: torch.Tensor) -> torch.Tensor:
        features = self.stem(clips)
        features = self.layer1(features)
        features = self.layer2(features)
        features = self.layer3(features)
        return self.layer4(features)


class GaoCineRegressor(nn.Module):
    """Published-style R(2+1)D cine regressor for EF learning."""

    def __init__(self, pretrained: bool = True):
        super().__init__()
        self.encoder = R2Plus1DEncoder(pretrained)
        self.head = nn.Linear(self.encoder.channels, 1)

    def forward(self, clips: torch.Tensor) -> torch.Tensor:
        features = self.encoder(clips).mean(dim=(2, 3, 4))
        return self.head(features).squeeze(1)
