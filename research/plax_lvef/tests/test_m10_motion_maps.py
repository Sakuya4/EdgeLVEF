import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
import torch
from plax_lvef.motion_maps import cycle_window, sample_motion_map, median_anchor, MotionFusion


def test_flat_cycle_falls_back():
    assert cycle_window(np.ones(64)*30)==(0,63,False)


def test_periodic_curve_has_cycle_and_keeps_original_amplitude():
    curve=30+8*np.cos(np.arange(64)*2*np.pi/20)
    a,b,valid=cycle_window(curve)
    assert valid and 18<=b-a<=22
    assert np.ptp(curve[a:b+1])>15


def test_motion_map_orientation_and_translation():
    cine=np.zeros((16,112,112),dtype=np.uint8)
    for t in range(16):
        cine[t,40+t,:]=255
    maps=sample_motion_map(cine,np.array([[56,28],[56,80]]))
    assert maps.shape==(5,80,128)
    assert maps.dtype==np.uint8
    assert np.argmax(maps[2,:,0])<np.argmax(maps[2,:,-1])


def test_zero_initial_correction_preserves_m5_and_gradient():
    for use_motion in (False,True):
        model=MotionFusion(use_motion)
        feature=torch.randn(2,256); ef=torch.tensor([30.,60.]); low=torch.randn(2)
        predicted,logit,projected=model(feature,ef,low,torch.rand(2,5,80,128))
        assert torch.equal(predicted,ef) and torch.equal(logit,low)
        assert projected.shape==(2,512)
        (predicted.sum()+logit.sum()).backward()
        assert model.ef.weight.grad.abs().sum()>0


def test_degenerate_anchor_is_rejected():
    import pytest
    with pytest.raises(ValueError):
        sample_motion_map(np.zeros((16,112,112),np.uint8),np.zeros((2,2)))


def test_valid_individual_lines_can_have_degenerate_median():
    points=np.array([[[50,30],[50,70]],[[50,70],[50,30]]], dtype=np.float32)
    anchor, coverage=median_anchor(points, np.ones(2,dtype=bool))
    assert coverage==0
    assert np.array_equal(anchor, [[56,28],[56,80]])
    maps=sample_motion_map(np.zeros((16,112,112),np.uint8),anchor)
    assert maps.shape==(5,80,128)


def test_valid_median_anchor_is_preserved():
    points=np.array([[[50,30],[50,70]],[[52,32],[52,72]]], dtype=np.float32)
    anchor, coverage=median_anchor(points,np.ones(2,dtype=bool))
    assert coverage==1
    assert np.array_equal(anchor,[[51,31],[51,71]])
