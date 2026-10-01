import torch

from edgelvef.research import EdgeLvefStudent, GaoR2Plus1DTeacher


def test_m5_teacher_parameter_count_matches_frozen_artifact():
    model = GaoR2Plus1DTeacher(pretrained=False)
    assert sum(parameter.numel() for parameter in model.parameters()) == 31_300_638


def test_m5_student_outputs_and_parameter_count():
    model = EdgeLvefStudent(pretrained=False).eval()
    with torch.inference_mode():
        lvef, trajectory, low_ef_logit, embedding = model(
            torch.zeros(1, 4, 1, 64, 64), return_embedding=True
        )
    assert sum(parameter.numel() for parameter in model.parameters()) == 1_118_275
    assert lvef.shape == (1,)
    assert trajectory.shape == (1, 4)
    assert low_ef_logit.shape == (1,)
    assert embedding.shape == (1, 256)
