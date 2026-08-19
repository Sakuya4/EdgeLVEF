# Model card: EdgeLVEF Student v4

## Intended use

Research evaluation of PLAX-compatible echocardiography cines. The model
produces an experimental continuous LVEF estimate and an uncalibrated low-EF
score. It is not intended for patient diagnosis, treatment decisions, or use
without clinician review.

## Architecture

- MobileNetV3-Small grayscale frame encoder
- 32 uniformly sampled frames at 112 x 112 pixels
- Three depthwise temporal residual blocks with dilations 1, 2, and 4
- Continuous LVEF and low-EF auxiliary heads
- Five fold-specific checkpoints supplied for external ensemble testing

## Evaluation

Exam-level five-fold out-of-fold evaluation used 164 real reference exams, 18
of which had LVEF <= 40%. Continuous LVEF MAE was 6.00 percentage points
(95% bootstrap CI 5.28--6.79), RMSE was 7.76, and Pearson r was 0.298. The
auxiliary low-EF AUROC was 0.694. At the literal continuous-output cutoff of
40%, sensitivity was zero because predictions contracted toward the training
population mean.

The reported metrics describe fold-specific out-of-fold predictions. They do
not constitute external, prospective, or clinical validation of the bundled
five-checkpoint ensemble.

## Important limitations

- PLAX-only; A4C input is outside scope.
- Severe low-EF cases are underrepresented.
- Predictions regress toward the population mean.
- Performance across scanners, hospitals, compression pipelines, and actual
  bedside acquisition has not been established.
- The low-EF probability is not externally calibrated.
- The model does not include the PLAX readiness gate in this release.
- Model-to-model standard deviation is not a clinical confidence interval.

## Training-data attribution

Training used EchoXFlow-derived research data. EchoXFlow is released by the
Ahus-AIM project under CC BY-NC-SA 4.0:
https://huggingface.co/datasets/Ahus-AIM/EchoXFlow

No patient images or source dataset files are redistributed here.
