# EdgeLVEF model cards

The repository contains four research generations:

1. **M5 Teacher/Student**, the current direct-video research candidate. The
   31.3M-parameter R(2+1)D Teacher is distilled into a 1.118M-parameter
   MobileNetV3-Small+TSM Student. Architecture and aggregate results are public;
   credentialed-data-derived weights are not. See
   [docs/models/m5-teacher-student.md](docs/models/m5-teacher-student.md).
2. **M1-LVEF3**, the current interpretable PLAX LVEF development candidate. See
   [docs/models/m1-lvef3.md](docs/models/m1-lvef3.md).
3. **Student Model**, the previous wall-motion deployment candidate. See
   [docs/models/student-model.md](docs/models/student-model.md).
4. **Student v4 direct-regression ensemble**, retained under
   `checkpoints/student_v4/` as a legacy reproducibility baseline. Its
   exam-level five-fold out-of-fold MAE was 6.00 percentage points and low-EF
   AUROC was 0.694. It regressed strongly toward the mean and is not the
   recommended board target.

None has prospective or external clinical validation. None is a medical device.
