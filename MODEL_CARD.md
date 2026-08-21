# EdgeLVEF model cards

The repository contains two research generations:

1. **Wall Student v12**, the current deployment candidate. See
   [docs/models/wall-student-v12.md](docs/models/wall-student-v12.md).
2. **Student v4 direct-regression ensemble**, retained under
   `checkpoints/student_v4/` as a legacy reproducibility baseline. Its
   exam-level five-fold out-of-fold MAE was 6.00 percentage points and low-EF
   AUROC was 0.694. It regressed strongly toward the mean and is not the
   recommended board target.

Neither model has prospective or external clinical validation. Neither is a
medical device.
