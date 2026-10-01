# M5 Teacher and Edge Student

This directory documents the frozen M5-A Teacher ensemble and M5-E edge
Student. It intentionally contains no model weights.

The models were trained from credentialed MIMIC-IV-ECHO data. PhysioNet states
that derived datasets and models must be treated as sensitive resources and,
when shared, distributed through PhysioNet under the same agreement as the
source data. The public GitHub repository therefore provides architecture,
aggregate metrics, artifact hashes and reproducibility code only.

Credentialed collaborators may place the three checkpoints in a private local
directory and verify them against `artifact_manifest.json`. Do not commit the
checkpoints, predictions, manifests containing patient/study identifiers, or
cached frames.

Architecture definitions:

- `edgelvef.research.GaoR2Plus1DTeacher`
- `edgelvef.research.EdgeLvefStudent`

See `docs/models/m5-teacher-student.md` for the model card and evidence limits.
