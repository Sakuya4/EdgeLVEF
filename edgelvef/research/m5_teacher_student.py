"""Frozen M5 Teacher and edge Student architecture definitions.

Weights trained from credentialed MIMIC-IV-ECHO data are intentionally not
distributed in this public repository. These definitions reproduce the module
names used by the restricted checkpoints.
"""

from __future__ import annotations

import torch
from torch import nn
from torchvision import models
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


class GaoR2Plus1DTeacher(nn.Module):
    """Published-style M5-A cine-level R(2+1)D LVEF Teacher."""

    def __init__(self, pretrained: bool = True):
        super().__init__()
        self.encoder = R2Plus1DEncoder(pretrained)
        self.head = nn.Linear(self.encoder.channels, 1)

    def forward(
        self, clips: torch.Tensor, return_embedding: bool = False
    ) -> torch.Tensor | tuple[torch.Tensor, torch.Tensor]:
        embedding = self.encoder(clips).mean(dim=(2, 3, 4))
        prediction = self.head(embedding).squeeze(1)
        if return_embedding:
            return prediction, embedding
        return prediction


def temporal_shift(feature_map: torch.Tensor, fold_div: int = 8) -> torch.Tensor:
    if feature_map.ndim != 5:
        raise ValueError("Expected [batch,time,channels,height,width]")
    fold = feature_map.shape[2] // fold_div
    if fold == 0 or feature_map.shape[1] < 2:
        return feature_map
    shifted = torch.zeros_like(feature_map)
    shifted[:, :-1, :fold] = feature_map[:, 1:, :fold]
    shifted[:, 1:, fold : 2 * fold] = feature_map[:, :-1, fold : 2 * fold]
    shifted[:, :, 2 * fold :] = feature_map[:, :, 2 * fold :]
    return shifted


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


def _grayscale_conv(first: nn.Conv2d) -> nn.Conv2d:
    grayscale = nn.Conv2d(
        1,
        first.out_channels,
        kernel_size=first.kernel_size,
        stride=first.stride,
        padding=first.padding,
        bias=False,
    )
    with torch.no_grad():
        grayscale.weight.copy_(first.weight.sum(dim=1, keepdim=True))
    return grayscale


def _frame_encoder(variant: str, pretrained: bool) -> tuple[nn.Module, int]:
    weights = "DEFAULT" if pretrained else None
    if variant == "mobilenet_v3_small":
        network = models.mobilenet_v3_small(weights=weights)
        feature_dim = 576
        network.features[0][0] = _grayscale_conv(network.features[0][0])
        encoder = network.features
    elif variant == "mobilenet_v3_large":
        network = models.mobilenet_v3_large(weights=weights)
        feature_dim = 960
        network.features[0][0] = _grayscale_conv(network.features[0][0])
        encoder = network.features
    elif variant == "mobilenet_v2":
        network = models.mobilenet_v2(weights=weights)
        feature_dim = 1280
        network.features[0][0] = _grayscale_conv(network.features[0][0])
        encoder = network.features
    elif variant == "shufflenet_v2_x1_0":
        network = models.shufflenet_v2_x1_0(weights=weights)
        feature_dim = 1024
        network.conv1[0] = _grayscale_conv(network.conv1[0])
        encoder = nn.Sequential(
            network.conv1,
            network.maxpool,
            network.stage2,
            network.stage3,
            network.stage4,
            network.conv5,
        )
    elif variant == "efficientnet_b0":
        network = models.efficientnet_b0(weights=weights)
        feature_dim = 1280
        network.features[0][0] = _grayscale_conv(network.features[0][0])
        encoder = network.features
    elif variant == "resnet18":
        network = models.resnet18(weights=weights)
        feature_dim = 512
        network.conv1 = _grayscale_conv(network.conv1)
        encoder = nn.Sequential(
            network.conv1,
            network.bn1,
            network.relu,
            network.maxpool,
            network.layer1,
            network.layer2,
            network.layer3,
            network.layer4,
        )
    else:
        raise ValueError(f"Unknown Student backbone: {variant}")
    return encoder, feature_dim


class EdgeLvefStudent(nn.Module):
    """2-D frame encoder with temporal shift and a compact temporal head."""

    def __init__(
        self,
        variant: str = "mobilenet_v3_small",
        pretrained: bool = True,
        label_mean: float = 50.0,
        label_std: float = 10.0,
    ):
        super().__init__()
        self.variant = variant
        self.encoder, feature_dim = _frame_encoder(variant, pretrained)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.volume_head = nn.Linear(feature_dim, 1)
        self.frame_projection = nn.Sequential(
            nn.Linear(feature_dim, 128), nn.Hardswish()
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
        self.temporal_dim = 256
        self.register_buffer("label_mean", torch.tensor(float(label_mean)))
        self.register_buffer("label_std", torch.tensor(float(label_std)))

    def encode_frames(self, frames: torch.Tensor) -> torch.Tensor:
        batch, time, channels, height, width = frames.shape
        encoded = frames.reshape(batch * time, channels, height, width)
        shift_index = max(len(self.encoder) - 4, 1)
        for index, module in enumerate(self.encoder):
            if index == shift_index:
                _, feature_channels, feature_height, feature_width = encoded.shape
                encoded = temporal_shift(
                    encoded.reshape(
                        batch,
                        time,
                        feature_channels,
                        feature_height,
                        feature_width,
                    )
                ).reshape(
                    batch * time,
                    feature_channels,
                    feature_height,
                    feature_width,
                )
            encoded = module(encoded)
        return self.pool(encoded).flatten(1).reshape(batch, time, -1)

    def forward(
        self, frames: torch.Tensor, return_embedding: bool = False
    ):
        features = self.encode_frames(frames)
        sequence = self.frame_projection(features).transpose(1, 2)
        sequence = self.temporal_blocks(sequence)
        embedding = torch.cat(
            [sequence.mean(dim=2), sequence.amax(dim=2)], dim=1
        )
        normalized_lvef = self.temporal_head(embedding).squeeze(1)
        lvef = normalized_lvef * self.label_std + self.label_mean
        trajectory = torch.sigmoid(self.volume_head(features).squeeze(2))
        low_ef_logit = self.low_ef_head(embedding).squeeze(1)
        if return_embedding:
            return lvef, trajectory, low_ef_logit, embedding
        return lvef, trajectory, low_ef_logit
