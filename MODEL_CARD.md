# EdgeLVEF model specification

The selected video model estimates LVEF from PLAX cines with a MobileNetV3-Large Student and offline R(2+1)D-18 ensemble supervision.

| Component | Specification |
|---|---|
| Teacher ensemble | Two R(2+1)D-18 networks; 62,601,276 parameters total |
| Student | MobileNetV3-Large + temporal shift + depthwise temporal CNN |
| Student parameters | 3,212,755 |
| Student input | 32 grayscale frames at 112 × 112 |
| Student outputs | Continuous LVEF and low-EF score |
| Training targets | Report-linked EF, Teacher EF, low-EF soft target and Teacher feature |
| Aggregation | Mean cine predictions within each study |

Read the [method](research/plax_lvef/METHOD.md), [Teacher specification](research/plax_lvef/TEACHER_MODEL_CARD.md), [Student specification](research/plax_lvef/STUDENT_MODEL_CARD.md), and [results](research/plax_lvef/RESULTS.md).

The [Readiness Gate](docs/models/readiness-gate.md) is an independent input-assessment module. It uses MobileNetV3-Small and five-frame pooling to output view, readiness and quality summaries.

Architecture and aggregate results are public. Trained LVEF weights and credentialed records remain in access-controlled storage. See [artifact terms](WEIGHTS_LICENSE.md).
