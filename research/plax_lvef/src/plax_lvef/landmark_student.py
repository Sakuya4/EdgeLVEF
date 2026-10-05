from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision.models import (
    ConvNeXt_Tiny_Weights,
    EfficientNet_B0_Weights,
    MobileNet_V2_Weights,
    MobileNet_V3_Large_Weights,
    MobileNet_V3_Small_Weights,
    ResNet18_Weights,
    ShuffleNet_V2_X1_0_Weights,
    convnext_tiny,
    efficientnet_b0,
    mobilenet_v2,
    mobilenet_v3_large,
    mobilenet_v3_small,
    resnet18,
    shufflenet_v2_x1_0,
)


LANDMARK_NAMES = ("lv-ivs-top", "lv-ivs-bottom", "lv-pw-top", "lv-pw-bottom")
ARCHITECTURES = (
    "mobilenet_v2",
    "mobilenet_v3_small",
    "mobilenet_v3_large",
    "shufflenet_v2_x1_0",
    "efficientnet_b0",
    "resnet18",
    "convnext_tiny",
)


class FpnDecoder(nn.Module):
    def __init__(self, channels: tuple[int, ...], output_channels: int = 4, width: int = 64):
        super().__init__()
        self.laterals = nn.ModuleList([nn.Conv2d(value, width, 1) for value in channels])
        self.smooth = nn.ModuleList(
            [
                nn.Sequential(
                    nn.Conv2d(width, width, 3, padding=1, bias=False),
                    nn.BatchNorm2d(width),
                    nn.SiLU(),
                )
                for _ in channels[:-1]
            ]
        )
        self.head = nn.Sequential(
            nn.Conv2d(width, width, 3, padding=1),
            nn.SiLU(),
            nn.Conv2d(width, output_channels, 1),
        )

    def forward(self, features: list[torch.Tensor], output_size: tuple[int, int]) -> torch.Tensor:
        pyramid = self.laterals[-1](features[-1])
        for level in range(len(features) - 2, -1, -1):
            pyramid = F.interpolate(
                pyramid, size=features[level].shape[-2:], mode="bilinear", align_corners=False
            )
            pyramid = self.smooth[level](pyramid + self.laterals[level](features[level]))
        return F.interpolate(self.head(pyramid), size=output_size, mode="bilinear", align_corners=False)


class MobileNetV3SmallFpn(nn.Module):
    def __init__(self, pretrained: bool):
        super().__init__()
        weights = MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
        self.encoder = mobilenet_v3_small(weights=weights).features
        self.decoder = FpnDecoder((16, 24, 48, 576))

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        output_size = image.shape[-2:]
        features = []
        for index, block in enumerate(self.encoder):
            image = block(image)
            if index in {1, 3, 8, 12}:
                features.append(image)
        return self.decoder(features, output_size)


class MobileNetV2Fpn(nn.Module):
    def __init__(self, pretrained: bool):
        super().__init__()
        weights = MobileNet_V2_Weights.DEFAULT if pretrained else None
        self.encoder = mobilenet_v2(weights=weights).features
        self.decoder = FpnDecoder((24, 32, 96, 1280))

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        output_size = image.shape[-2:]
        features = []
        for index, block in enumerate(self.encoder):
            image = block(image)
            if index in {3, 6, 13, 18}:
                features.append(image)
        return self.decoder(features, output_size)


class MobileNetV3LargeFpn(nn.Module):
    def __init__(self, pretrained: bool):
        super().__init__()
        weights = MobileNet_V3_Large_Weights.DEFAULT if pretrained else None
        self.encoder = mobilenet_v3_large(weights=weights).features
        self.decoder = FpnDecoder((24, 40, 112, 960))

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        output_size = image.shape[-2:]
        features = []
        for index, block in enumerate(self.encoder):
            image = block(image)
            if index in {3, 6, 12, 16}:
                features.append(image)
        return self.decoder(features, output_size)


class ShuffleNetV2Fpn(nn.Module):
    def __init__(self, pretrained: bool):
        super().__init__()
        weights = ShuffleNet_V2_X1_0_Weights.DEFAULT if pretrained else None
        network = shufflenet_v2_x1_0(weights=weights)
        self.conv1 = network.conv1
        self.maxpool = network.maxpool
        self.stages = nn.ModuleList([network.stage2, network.stage3, network.stage4])
        self.decoder = FpnDecoder((24, 116, 232, 464))

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        output_size = image.shape[-2:]
        image = self.maxpool(self.conv1(image))
        features = [image]
        for stage in self.stages:
            image = stage(image)
            features.append(image)
        return self.decoder(features, output_size)


class EfficientNetB0Fpn(nn.Module):
    def __init__(self, pretrained: bool):
        super().__init__()
        weights = EfficientNet_B0_Weights.DEFAULT if pretrained else None
        self.encoder = efficientnet_b0(weights=weights).features
        self.decoder = FpnDecoder((24, 40, 112, 1280))

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        output_size = image.shape[-2:]
        features = []
        for index, block in enumerate(self.encoder):
            image = block(image)
            if index in {2, 3, 5, 8}:
                features.append(image)
        return self.decoder(features, output_size)


class ResNet18Fpn(nn.Module):
    def __init__(self, pretrained: bool):
        super().__init__()
        weights = ResNet18_Weights.DEFAULT if pretrained else None
        network = resnet18(weights=weights)
        self.stem = nn.Sequential(network.conv1, network.bn1, network.relu, network.maxpool)
        self.layers = nn.ModuleList([network.layer1, network.layer2, network.layer3, network.layer4])
        self.decoder = FpnDecoder((64, 128, 256, 512))

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        output_size = image.shape[-2:]
        image = self.stem(image)
        features = []
        for layer in self.layers:
            image = layer(image)
            features.append(image)
        return self.decoder(features, output_size)


class ConvNeXtTinyFpn(nn.Module):
    def __init__(self, pretrained: bool):
        super().__init__()
        weights = ConvNeXt_Tiny_Weights.DEFAULT if pretrained else None
        self.features = convnext_tiny(weights=weights).features
        self.decoder = FpnDecoder((96, 192, 384, 768))

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        output_size = image.shape[-2:]
        features = []
        for index, block in enumerate(self.features):
            image = block(image)
            if index in {1, 3, 5, 7}:
                features.append(image)
        return self.decoder(features, output_size)


def build_landmark_model(architecture: str, pretrained: bool = True) -> nn.Module:
    if architecture == "mobilenet_v2":
        return MobileNetV2Fpn(pretrained)
    if architecture == "mobilenet_v3_small":
        return MobileNetV3SmallFpn(pretrained)
    if architecture == "mobilenet_v3_large":
        return MobileNetV3LargeFpn(pretrained)
    if architecture == "shufflenet_v2_x1_0":
        return ShuffleNetV2Fpn(pretrained)
    if architecture == "efficientnet_b0":
        return EfficientNetB0Fpn(pretrained)
    if architecture == "resnet18":
        return ResNet18Fpn(pretrained)
    if architecture == "convnext_tiny":
        return ConvNeXtTinyFpn(pretrained)
    raise ValueError(f"Unknown architecture: {architecture}")


def supervised_heatmap_loss(logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
    positive_weight = torch.full((4, 1, 1), 20.0, device=logits.device)
    bce = F.binary_cross_entropy_with_logits(logits, targets, pos_weight=positive_weight)
    probabilities = torch.sigmoid(logits)
    intersection = (probabilities * targets).sum(dim=(-2, -1))
    dice = (2 * intersection + 1) / (
        probabilities.sum(dim=(-2, -1)) + targets.sum(dim=(-2, -1)) + 1
    )
    return bce + 1 - dice.mean()


def soft_consistency_loss(logits: torch.Tensor, teacher_probabilities: torch.Tensor) -> torch.Tensor:
    probabilities = torch.sigmoid(logits)
    confidence = teacher_probabilities.amax(dim=(-2, -1), keepdim=True).detach()
    spatial_weight = 1.0 + 15.0 * teacher_probabilities
    weight = confidence * spatial_weight
    return ((probabilities - teacher_probabilities).square() * weight).sum() / weight.sum().clamp_min(1.0)
