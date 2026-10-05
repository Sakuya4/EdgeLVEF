"""Frozen M1 locator adapter; no checkpoint or clinical accuracy claim."""
import torch
from plax_lvef.landmark_student import ResNet18Fpn, FpnDecoder


def build_teacher(checkpoint_path):
    model = ResNet18Fpn(pretrained=False)
    model.decoder = FpnDecoder((64,128,256,512), output_channels=8)
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    model.load_state_dict(checkpoint["model"])
    return model


def soft_coordinates(logits):
    probability = torch.sigmoid(logits).square()
    probability = probability / probability.sum(dim=(-2,-1),keepdim=True).clamp_min(1e-6)
    height,width = logits.shape[-2:]
    yy,xx = torch.meshgrid(torch.arange(height,device=logits.device,dtype=logits.dtype),
                          torch.arange(width,device=logits.device,dtype=logits.dtype),indexing="ij")
    return torch.stack(((probability*xx).sum(dim=(-2,-1)),
                        (probability*yy).sum(dim=(-2,-1))),dim=-1)
