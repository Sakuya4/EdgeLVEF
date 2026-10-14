# Manuscript writing prompt

Read the repository at https://github.com/Sakuya4/EdgeLVEF and prepare an English LaTeX research report about its PLAX-only Teacher–Student video model.

Use these files as the source:

1. `README.md` and `research/plax_lvef/METHOD.md`: motivation, research origin and method.
2. `docs/architecture.md`: learning and device architecture.
3. `research/plax_lvef/TEACHER_MODEL_CARD.md` and `STUDENT_MODEL_CARD.md`: component specifications.
4. `research/plax_lvef/RESULTS.md` and its linked aggregate data: model comparisons and EF-error statistics.
5. `research/plax_lvef/REFERENCES.md`: research foundations.
6. `research/plax_lvef/src/plax_lvef/model.py` and `study_video.py`: implemented architecture.

Write in the authors' voice using “we.” Organize the report around portable PLAX acquisition, spatiotemporal representation transfer, compact inference and the controlled six-backbone comparison. Use descriptive method names such as “Teacher ensemble,” “edge Student” and “PLAX Readiness Gate.” Explain the Student's temporal shift, 128-channel residual temporal path, mean/max pooling and training-only feature projector.

Present the 82-study benchmark and the 54-study report-EF reassessment as separate cohorts. Define MAE in percentage points. Keep screening-head metrics separate from numerical EF ≤ 40% metrics. Use exact statistics and coefficient values from the source files. Parameter reduction describes model size; latency, power and NPU execution require their own measured evidence.

Prepare a two-panel architecture figure: (a) offline Teacher–Student learning with the four supervision terms; (b) Student inference from 32-frame PLAX cine to LVEF and low-EF score. Readiness and device acquisition are system modules. Use a restrained black-and-white conference style.

Include an abstract, introduction, related work, methods, evaluation protocol, results, system implementation and conclusion. Use IEEE numbered references and cite the original works for R(2+1)D, MobileNetV3 and TSM. Discuss contributions through the implemented task adaptation and efficiency/accuracy comparison. Do not invent publications, experiment results, patient counts, hardware measurements or clinical claims.

The repository provides architecture and source, not trained LVEF weights. Produce editable `.tex` and bibliography sources, with tables traceable to the aggregate files.
