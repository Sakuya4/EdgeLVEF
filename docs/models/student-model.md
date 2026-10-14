# LV wall-tracking module

This measurement adapter extracts two opposing endocardial wall trajectories from PLAX-compatible cines. Its geometry layer supplies temporal smoothing, ED/ES candidate selection and fractional-shortening features.

| Property | Value |
|---|---|
| Architecture | MobileNetV3-Small with two wall-logit outputs |
| Parameters | 985,634 |
| Input | RGB NCHW, ImageNet normalization, 320 × 320 |
| Output | Two wall-logit maps, 320 × 320 |
| Runtime | FP32 ONNX; opset 17 |
| Artifact size | 3,955,338 bytes |

Grayscale inputs are resized and repeated to RGB. The adapter is used by the existing measurement and overlay commands described in the [application guide](../application.md). The selected video-regression Student is specified separately in [the research package](../../research/plax_lvef/STUDENT_MODEL_CARD.md).

The immutable artifact, scalar head configuration and checksums remain under `models/student_model/`. Runtime verification compares output shapes, finite values and configured checksums.
