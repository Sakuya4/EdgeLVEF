# EdgeLVEF model cards

The repository contains three research generations:

1. **M1-LVEF3**, the current interpretable PLAX LVEF development candidate. See
   [docs/models/m1-lvef3.md](docs/models/m1-lvef3.md).
2. **Student Model**, the previous wall-motion deployment candidate. See
   [docs/models/student-model.md](docs/models/student-model.md).
3. **Student v4 direct-regression ensemble**, retained under
   `checkpoints/student_v4/` as a legacy reproducibility baseline. Its
   exam-level five-fold out-of-fold MAE was 6.00 percentage points and low-EF
   AUROC was 0.694. It regressed strongly toward the mean and is not the
   recommended board target.

Neither model has prospective or external clinical validation. Neither is a
medical device.
