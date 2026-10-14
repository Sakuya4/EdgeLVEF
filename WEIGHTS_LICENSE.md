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

The Readiness Gate under `models/readiness_gate/` is the thesis R1 multi-task
candidate trained with EchoUNAL view labels and EchoNet-LVH anatomy-derived
quality/readiness proxy labels. Its dataset attribution is EchoUNAL and
EchoNet-LVH, rather than EchoXFlow. The existing non-commercial research and
evaluation terms above apply subject to upstream rights; this repository cannot
grant rights that the team does not hold. No credentialed MIMIC data or
foundation Teacher derivatives are included in this R1 artifact.

The Student Model was trained from EchoXFlow target-domain data using
Teacher-generated wall paths. Redistribution or commercial use must also be
reviewed against the upstream Teacher/model terms; this repository does not
grant rights beyond those upstream terms.

The LVID tracker was trained from EchoNet-LVH measurement annotations and
initialized from the measurement Student. Its scalar calibration was fitted
on EchoXFlow development labels. Users must separately review and comply with
the upstream dataset and pretrained-weight terms; this repository does not
expand those rights.

The video Teacher and Student weights are not distributed in this repository.
They were trained from credentialed MIMIC-IV-ECHO data. PhysioNet guidance
states that derived datasets and models are sensitive resources and should be
shared through PhysioNet under the same agreement as the source data. Public
files are limited to architecture code, aggregate results and artifact hashes.
