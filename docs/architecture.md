# EdgeLVEF architecture

EdgeLVEF separates offline learning from device inference. The Teacher learns spatiotemporal features during model development; the Student carries the video analysis path on the target device. Input assessment and acquisition are separate modules with explicit interfaces.

## A. Offline learning

![Teacher–Student learning and Student inference](assets/edgelvef-architecture.png)

Figure 1. Teacher and feature projector participate in offline learning. Student inference integrates frame encoding, temporal exchange, dilated temporal processing and pooled predictions. Dashed arrows denote supervision; the Readiness Gate is a separate system module.

| Stage | Input | Computation | Output |
|---|---|---|---|
| Teacher learning | 64-frame PLAX clips and report-linked EF | Two R(2+1)D-18 cine regressors | Ensemble EF and 512-D representation |
| Student spatial encoding | 32 grayscale frames, 112 × 112 | MobileNetV3-Large; temporal shift before the final four encoder blocks | 960-D feature per frame |
| Student temporal encoding | Frame feature sequence | 960 → 128 projection; residual depthwise temporal convolutions with dilations 1, 2, 4 | 128-channel temporal sequence |
| Video pooling | Temporal sequence | Concatenate temporal mean and maximum pooling | 256-D video feature |
| Prediction and transfer | Video feature and training targets | EF regression head, low-EF head, training-only 256 → 512 projector | Supervised and distilled learning objectives |

The training objective combines report EF, ensemble EF, Teacher-derived low-EF soft targets and cosine feature alignment. The [method](../research/plax_lvef/METHOD.md) specifies the coefficients and optimization settings.

## B. Device inference

The analysis contract accepts a PLAX cine and returns an LVEF estimate and low-EF score. The Student performs frame encoding, temporal integration and prediction without Teacher inference. For study-level analysis, predictions from eligible cines are averaged.

The PLAX Readiness Gate processes five-frame windows with a MobileNetV3-Small encoder and feature pooling. Separate heads produce view, four-level readiness and five quality outputs. These describe input conditions and are separate from the Student's EF estimate.

The acquisition design uses an authorized Aco Android SDK in a headless runtime on i.MX93. A board-local Unix socket transports image frames to the native Linux application. The interface displays ultrasound and analysis; the acquisition adapter owns reconnection and stream handling.

| System component | Responsibility | Implementation |
|---|---|---|
| Acquisition | Receive P42 images through the authorized SDK and local transport | `hardware/aco-p42-imx93-headless-sidecar/` |
| Input assessment | View, readiness and quality summary | `edgelvef/application/assess_readiness.py` |
| Video model | Compact spatiotemporal LVEF network | `research/plax_lvef/src/plax_lvef/model.py` |
| Application | Video display, result presentation and measurement sessions | `edgelvef_app/` |
| Runtime adapters | Decode inputs, load configured artifacts and record execution metadata | `edgelvef/infrastructure/` |

## Source organization

The application follows inward dependency boundaries. Domain functions contain geometry and numeric rules. Application use cases coordinate domain logic through ports. Infrastructure provides video, model-runtime and configuration adapters; interfaces handle CLI and UI input.

The importable video architecture is defined in `edgelvef/research/video_distillation.py`. The training package includes the six-backbone implementation, authorized-data loaders and optimization scripts. Existing measurement adapters remain available to their operator commands; research model definitions are maintained independently of hardware configuration.

## Deployment design

The target is an Embedded Linux device with local image processing. Model conversion, execution-provider selection and the complete temporal path are explicit parts of the deployment design. Architecture size is reported as parameter count; device performance is recorded separately by the hardware evaluation procedures.
