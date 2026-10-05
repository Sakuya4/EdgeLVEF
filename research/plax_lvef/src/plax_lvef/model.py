from __future__ import annotations

import torch
from torch import nn
from torchvision import models


LVEF_BACKBONES = (
    "mobilenet_v2",
    "mobilenet_v3_small",
    "mobilenet_v3_large",
    "shufflenet_v2_x1_0",
    "efficientnet_b0",
    "resnet18",
    "convnext_tiny",
)


def temporal_shift(feature_map: torch.Tensor, fold_div: int = 8) -> torch.Tensor:
    """Exchange a fraction of feature channels with adjacent video frames."""
    if feature_map.ndim != 5:
        raise ValueError("Expected feature map [batch,time,channels,height,width]")
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
    elif variant == "convnext_tiny":
        network = models.convnext_tiny(weights=weights)
        feature_dim = 768
        network.features[0][0] = _grayscale_conv(network.features[0][0])
        encoder = network.features
    else:
        raise ValueError(f"Unknown model variant: {variant}")
    return encoder, feature_dim


class EdgeLvefModel(nn.Module):
    """2-D NPU frame encoder with a small temporal head."""

    def __init__(
        self,
        variant: str = "mobilenet_v3_small",
        pretrained: bool = True,
        label_mean: float = 50.0,
        label_std: float = 10.0,
        temporal_model: str = "statistics",
    ):
        super().__init__()
        self.variant = variant
        self.temporal_model = temporal_model
        self.encoder, feature_dim = _frame_encoder(variant, pretrained)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.volume_head = nn.Linear(feature_dim, 1)
        if temporal_model == "statistics":
            temporal_dim = feature_dim * 5
            self.temporal_head = nn.Sequential(
                nn.Linear(temporal_dim, 256),
                nn.Hardswish(),
                nn.Dropout(0.2),
                nn.Linear(256, 1),
            )
        elif temporal_model in ("tcn", "tsm"):
            temporal_dim = 256
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
                nn.Linear(temporal_dim, 128),
                nn.Hardswish(),
                nn.Dropout(0.2),
                nn.Linear(128, 1),
            )
        else:
            raise ValueError(f"Unknown temporal model: {temporal_model}")
        self.temporal_dim = temporal_dim
        self.low_ef_head = nn.Sequential(
            nn.Linear(temporal_dim, 128),
            nn.Hardswish(),
            nn.Dropout(0.2),
            nn.Linear(128, 1),
        )
        self.encoder_frozen = False
        self.encoder_trainable_from: int | None = None
        self.register_buffer("label_mean", torch.tensor(float(label_mean)))
        self.register_buffer("label_std", torch.tensor(float(label_std)))

    def freeze_encoder(self) -> None:
        self.encoder_frozen = True
        self.encoder_trainable_from = None
        self.encoder.requires_grad_(False)
        self.encoder.eval()

    def train_encoder_last_stage(self) -> None:
        self.encoder_frozen = False
        self.encoder.requires_grad_(False)
        self.encoder_trainable_from = max(len(self.encoder) - 4, 0)
        for module in self.encoder[self.encoder_trainable_from :]:
            module.requires_grad_(True)

    def train(self, mode: bool = True):
        super().train(mode)
        if mode and self.encoder_frozen:
            self.encoder.eval()
        elif mode and self.encoder_trainable_from is not None:
            for module in self.encoder[: self.encoder_trainable_from]:
                module.eval()
        return self

    def encode_frames(self, frames: torch.Tensor) -> torch.Tensor:
        batch, time, channels, height, width = frames.shape
        encoded = frames.reshape(batch * time, channels, height, width)
        for index, module in enumerate(self.encoder):
            if self.temporal_model == "tsm" and index == max(len(self.encoder) - 4, 1):
                _, feature_channels, feature_height, feature_width = encoded.shape
                encoded = temporal_shift(
                    encoded.reshape(batch, time, feature_channels, feature_height, feature_width)
                ).reshape(batch * time, feature_channels, feature_height, feature_width)
            encoded = module(encoded)
        return self.pool(encoded).flatten(1).reshape(batch, time, -1)

    def forward(
        self,
        frames: torch.Tensor,
        return_embedding: bool = False,
    ):
        features = self.encode_frames(frames)
        if self.temporal_model == "statistics":
            delta = (features[:, 1:] - features[:, :-1]).abs().mean(dim=1)
            temporal_features = torch.cat(
                [
                    features.mean(dim=1),
                    features.std(dim=1, unbiased=False),
                    features.amax(dim=1),
                    features.amin(dim=1),
                    delta,
                ],
                dim=1,
            )
        else:
            sequence = self.frame_projection(features).transpose(1, 2)
            sequence = self.temporal_blocks(sequence)
            temporal_features = torch.cat(
                [sequence.mean(dim=2), sequence.amax(dim=2)],
                dim=1,
            )
        normalized_lvef = self.temporal_head(temporal_features).squeeze(1)
        lvef = normalized_lvef * self.label_std + self.label_mean
        volume_curve = torch.sigmoid(self.volume_head(features).squeeze(2))
        low_ef_logit = self.low_ef_head(temporal_features).squeeze(1)
        if return_embedding:
            return lvef, volume_curve, low_ef_logit, temporal_features
        return lvef, volume_curve, low_ef_logit


class FrameEncoderExport(nn.Module):
    """Deployment boundary intended for INT8 conversion and Ethos-U65."""

    def __init__(self, trained_model: EdgeLvefModel):
        super().__init__()
        self.encoder = trained_model.encoder
        self.pool = trained_model.pool
        self.volume_head = trained_model.volume_head

    def forward(self, frames: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        features = self.pool(self.encoder(frames)).flatten(1)
        volume_score = torch.sigmoid(self.volume_head(features))
        return features, volume_score
