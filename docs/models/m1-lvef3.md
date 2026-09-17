# M1-LVEF3 interpretable measurement pipeline

M1-LVEF3 is the current PLAX-only development candidate. It separates image
understanding from the numerical LVEF mapping:

1. A 978,214-parameter ShuffleNetV2-FPN predicts two LVID endpoints per frame.
2. The full-cine LVID trajectory is smoothed; its maximum and minimum define ED
   and ES candidates.
3. The system reports LVIDd, LVIDs and their ratio.
4. A three-parameter monotonic equation produces a development-calibrated LVEF.

The equation is:

```text
LVEF = clip(a + b * 100 * (1 - (LVIDs/LVIDd)^p), 0, 100)
```

The released balanced fit uses `a=-0.4812`, `b=0.6020`, and `p=3.7896`.

## Evidence

Five-fold examination-level nested development validation included 164
EchoXFlow examinations, 18 with same-exam 3-D mesh-derived LVEF <=40%.

| Metric | Result |
|---|---:|
| MAE | 5.236 percentage points |
| MAE 95% CI | 4.621--5.896 |
| Bias | -1.294 points |
| Pearson r | 0.601 |
| CCC | 0.555 |
| Sensitivity | 0.500 (9/18) |
| Specificity | 0.993 (145/146) |
| F1 | 0.643 |

The low-EF sensitivity interval was wide (0.263--0.733), one fold detected none
of three low-EF examinations, and the available reference range was only
25.75--67.06%. These results are development evidence, not an external or
clinical validation.

## Run

```bash
python scripts/run_m1_lvef3.py path/to/plax_cine.mp4 --fps 50
```

The JSON output includes the ED/ES frame indices, LVIDd, LVIDs, their ratio,
calibrated LVEF, endpoint confidence and whether the ratio lies inside the
central development range.
