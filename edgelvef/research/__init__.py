"""Research-only PyTorch architectures; not imported by the ONNX runtime path."""

from .m5_teacher_student import EdgeLvefStudent, GaoR2Plus1DTeacher

__all__ = ["EdgeLvefStudent", "GaoR2Plus1DTeacher"]
