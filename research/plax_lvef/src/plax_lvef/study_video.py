"""Study-level PLAX video models used by the locked M5 experiment."""

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
    """Published-style R(2+1)D cine regressor for the M5-A baseline."""

    def __init__(self, pretrained: bool = True):
        super().__init__()
        self.encoder = R2Plus1DEncoder(pretrained)
        self.head = nn.Linear(self.encoder.channels, 1)

    def forward(self, clips: torch.Tensor) -> torch.Tensor:
        features = self.encoder(clips).mean(dim=(2, 3, 4))
        return self.head(features).squeeze(1)


class GatedAttention(nn.Module):
    def __init__(self, channels: int, hidden: int):
        super().__init__()
        self.tanh = nn.Linear(channels, hidden)
        self.sigmoid = nn.Linear(channels, hidden)
        self.score = nn.Linear(hidden, 1, bias=False)

    def forward(
        self, features: torch.Tensor, mask: torch.Tensor | None = None
    ) -> tuple[torch.Tensor, torch.Tensor]:
        logits = self.score(torch.tanh(self.tanh(features)) * torch.sigmoid(self.sigmoid(features))).squeeze(-1)
        if mask is not None:
            logits = logits.masked_fill(~mask, torch.finfo(logits.dtype).min)
        weights = logits.softmax(dim=-1)
        return torch.sum(features * weights.unsqueeze(-1), dim=-2), weights


class StudyTemporalTeacher(nn.Module):
    """Shared cine encoder, temporal fusion, and study-level MIL aggregation."""

    def __init__(self, pretrained: bool = True, physiology_head: bool = False):
        super().__init__()
        self.encoder = R2Plus1DEncoder(pretrained)
        self.temporal_attention = GatedAttention(512, 128)
        self.cine_projection = nn.Sequential(
            nn.LayerNorm(1024), nn.Linear(1024, 256), nn.GELU(), nn.Dropout(0.2)
        )
        self.study_attention = GatedAttention(256, 128)
        self.shared_head = nn.Sequential(nn.LayerNorm(256), nn.Linear(256, 128), nn.GELU())
        self.ef_head = nn.Linear(128, 1)
        self.low_ef_head = nn.Linear(128, 1)
        self.ordinal_head = nn.Linear(128, 4)
        self.ratio_head = nn.Linear(128, 1) if physiology_head else None

    def encode_cines(self, clips: torch.Tensor) -> torch.Tensor:
        feature_map = self.encoder(clips)
        global_feature = feature_map.mean(dim=(2, 3, 4))
        temporal_tokens = feature_map.mean(dim=(3, 4)).transpose(1, 2)
        temporal_feature, _ = self.temporal_attention(temporal_tokens)
        return self.cine_projection(torch.cat((global_feature, temporal_feature), dim=1))

    def predict_from_embeddings(
        self, embeddings: torch.Tensor, mask: torch.Tensor | None = None
    ) -> dict[str, torch.Tensor]:
        study, cine_attention = self.study_attention(embeddings, mask)
        shared = self.shared_head(study)
        output = {
            "lvef": self.ef_head(shared).squeeze(-1),
            "low_ef_logit": self.low_ef_head(shared).squeeze(-1),
            "ordinal_logits": self.ordinal_head(shared),
            "cine_attention": cine_attention,
        }
        if self.ratio_head is not None:
            output["lvid_ratio"] = self.ratio_head(shared).sigmoid().squeeze(-1)
        return output

    def forward(self, clips: torch.Tensor, mask: torch.Tensor | None = None) -> dict[str, torch.Tensor]:
        batch, cines, channels, frames, height, width = clips.shape
        embeddings = self.encode_cines(clips.reshape(batch * cines, channels, frames, height, width))
        return self.predict_from_embeddings(embeddings.reshape(batch, cines, -1), mask)

    @torch.inference_mode()
    def predict_chunked(self, clips: torch.Tensor, chunk_size: int = 2) -> dict[str, torch.Tensor]:
        embeddings = [self.encode_cines(part) for part in clips.split(chunk_size)]
        return self.predict_from_embeddings(torch.cat(embeddings).unsqueeze(0))
