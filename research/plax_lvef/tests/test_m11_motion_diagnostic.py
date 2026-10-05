import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import torch

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "scripts"))
from run_m11_motion_diagnostic import transform_map, MotionOnly, paired_delta, previews
from run_m10_motion_fusion import check_splits


def test_shuffle_preserves_values_and_uses_one_order_for_all_lines():
    maps=torch.arange(128).expand(5,80,128).float()
    changed=transform_map(maps,"shuffled",4,20261005)
    assert not torch.equal(maps,changed)
    assert torch.equal(changed.sort(-1).values,maps)
    assert torch.equal(changed[0,0],changed[4,79])
    assert torch.equal(changed,transform_map(maps,"shuffled",4,20261005))


def test_static_removes_temporal_variation_but_preserves_mean():
    maps=torch.rand(5,80,128)
    static=transform_map(maps,"static",0,1)
    assert torch.allclose(static.mean(-1),maps.mean(-1),atol=1e-6)
    assert torch.all(static.std(-1)==0)


def test_motion_only_forward_and_all_parameters_receive_gradients():
    model=MotionOnly(50,15)
    ef,low,projected=model(torch.rand(2,5,80,128))
    assert ef.shape==low.shape==(2,)
    assert projected.shape==(2,512)
    (ef.sum()+low.sum()+projected.square().mean()).backward()
    for parameter in model.parameters():
        assert parameter.grad is not None and torch.isfinite(parameter.grad).all()


def test_patient_split_leakage_is_rejected():
    frame=pd.DataFrame({"subject_id":["a","a"],"study_id":["x","y"],"split":["train","test"],"lvef":[30,30]})
    with pytest.raises(ValueError,match="Patient"):
        check_splits(frame)


def test_paired_bootstrap_identity_is_zero():
    data=pd.DataFrame({"study_id":["x","y"],"reference_lvef":[30,60],"predicted_lvef":[35,55]})
    subjects=pd.DataFrame({"study_id":["x","y"],"subject_id":["a","a"]})
    result=paired_delta(data,data,subjects,1)
    assert result=={"delta_mae":0.,"ci_lower":0.,"ci_upper":0.}


def test_preview_accepts_legacy_integer_fallback_anchor(tmp_path):
    from argparse import Namespace
    cache=tmp_path / "cache"; cache.mkdir()
    cine=tmp_path / "dummy.npz"
    np.savez(cine,frames=np.zeros((4,112,112),np.uint8))
    np.savez(cache / "000000.npz",anchor=np.array([[56,28],[56,80]],dtype=np.int64),
             maps=np.zeros((3,5,80,128),np.uint8),valid_coverage=0.,cycle_ok=False)
    frame=pd.DataFrame({"split":["train","validation"],"cache_row":[0,0],"path":[str(cine),str(cine)]})
    args=Namespace(secure_output=tmp_path / "secure",summary_output=tmp_path / "summary",motion_cache=cache)
    previews(args,frame)
    assert len(list((args.secure_output / "previews").glob("*.png")))==2
