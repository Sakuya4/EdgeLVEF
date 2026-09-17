# Checkpoint terms

The model files under `checkpoints/` and `models/` are released for non-commercial
research and evaluation under the Creative Commons Attribution-NonCommercial-
ShareAlike 4.0 International license:

https://creativecommons.org/licenses/by-nc-sa/4.0/

Attribution must include this EdgeLVEF repository and the EchoXFlow dataset:
https://huggingface.co/datasets/Ahus-AIM/EchoXFlow

The checkpoints are supplied without warranties and are not approved for
clinical use. The Python source code has no separate open-source license grant
unless one is added by the repository owner.

The Student Model was trained from EchoXFlow target-domain data using
Teacher-generated wall paths. Redistribution or commercial use must also be
reviewed against the upstream Teacher/model terms; this repository does not
grant rights beyond those upstream terms.

The M1-LVEF3 tracker was trained from EchoNet-LVH measurement annotations and
initialized from the M1 measurement Student. Its scalar calibration was fitted
on EchoXFlow development labels. Users must separately review and comply with
the upstream dataset and pretrained-weight terms; this repository does not
expand those rights.
