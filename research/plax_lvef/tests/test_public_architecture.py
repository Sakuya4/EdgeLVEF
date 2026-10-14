import ast
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(REPO))

from plax_lvef.model import EdgeLvefModel
from plax_lvef.study_video import GaoCineRegressor
from edgelvef.research import EdgeLvefStudent, GaoR2Plus1DTeacher


def test_importable_student_matches_training_architecture():
    training = EdgeLvefModel(
        variant="mobilenet_v3_large", pretrained=False, temporal_model="tsm"
    ).eval()
    public = EdgeLvefStudent(variant="mobilenet_v3_large", pretrained=False).eval()
    public.load_state_dict(training.state_dict(), strict=True)
    sample = torch.zeros(1, 4, 1, 112, 112)
    with torch.inference_mode():
        expected = training(sample, return_embedding=True)
        actual = public(sample, return_embedding=True)
    for left, right in zip(expected, actual):
        torch.testing.assert_close(left, right)
    assert sum(p.numel() for p in public.parameters()) == 3_212_755


def test_teacher_checkpoint_modules_and_parameter_count():
    training = GaoCineRegressor(pretrained=False)
    public = GaoR2Plus1DTeacher(pretrained=False)
    public.load_state_dict(training.state_dict(), strict=True)
    assert sum(p.numel() for p in public.parameters()) == 31_300_638


def test_teacher_training_keeps_gradients_enabled():
    tree = ast.parse((ROOT / "scripts" / "train_teacher.py").read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "train_gao")
    assert not function.decorator_list


def test_public_training_contains_only_selected_distillation():
    source = (ROOT / "scripts" / "train_student.py").read_text(encoding="utf-8")
    assert "boundary_recovery" not in source
    assert "ordinal_head" not in source
    assert 'default="mobilenet_v3_large"' in source
