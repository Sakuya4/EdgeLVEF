"""Research-only PyTorch architectures; not imported by the ONNX runtime path."""

from .video_distillation import EdgeLvefStudent, GaoR2Plus1DTeacher

__all__ = ["EdgeLvefStudent", "GaoR2Plus1DTeacher"]
