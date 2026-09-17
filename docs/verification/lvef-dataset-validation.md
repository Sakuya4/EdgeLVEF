# Dataset workstation LVEF validation

This package travels with the repository to the workstation that owns the data.
It does not copy, rename, or modify EchoXFlow videos. D:\ and E:\ below are
example paths on that other workstation.

## Quick start

From the repository root on the data workstation:

~~~powershell
python test.py
~~~

If test_config.json exists, the run starts without path questions. Otherwise,
paste the manifest path and choose the output directory when prompted. Copy
test_config.example.json to test_config.json when a repeatable unattended run
is preferred.

The final line prints ZIP READY TO RETURN. Send that ZIP; it excludes original
video paths and pseudonymizes patient, exam, and recording IDs. The local run
directory keeps the full internal result for authorized review.
## Manifest

Copy research/manifests/strong_lvef_manifest.template.csv and add one row per
recording.

Required inference fields:

- exam_id
- recording_id
- video_path

Required evaluation reference:

- gt_lvef, or both edv and esv

Strongly required for defensible splitting:

- patient_id
- fold
- label_source

Useful bias fields:

- site
- vendor
- sex
- age_group

video_path may be an absolute path such as
D:\EchoXFlow\videos\exam001.mp4 or E:\EchoXFlow\exam001\plax.avi. Use the real
per-recording fps. crop is optional and uses x1,y1,x2,y2. Never copy pseudo
labels into gt_lvef.

## Step 1: batch M1-LVEF3 inference

Run from the repository root on the dataset workstation:

~~~powershell
python -m edgelvef.interfaces.cli.batch_lvef3 D:\EchoXFlow\strong_manifest.csv --output E:\EdgeLVEF_results\m1_lvef3_predictions.csv --default-fps 50
~~~

The command verifies the frozen ONNX SHA-256, loads the model once, writes after
every cine, records failures, and skips prior status=ok rows when resumed. The
default FPS is only a fallback; manifest FPS is preferred.

## Step 2: paired evaluation

~~~powershell
python -m edgelvef.interfaces.cli.evaluate_lvef E:\EdgeLVEF_results\m1_lvef3_predictions.csv --output-dir E:\EdgeLVEF_results\m1_lvef3_evaluation --require-patient-id --group-columns label_source,site,vendor,sex,age_group --bootstrap 2000
~~~

Outputs:

- metrics.json: complete result and bootstrap intervals
- report.md: readable cohort and metric summary
- exam_predictions.csv: one row per exam, error and TP/FN/TN/FP
- group_metrics.csv: site/vendor/demographic bias audit
- threshold_sweep.csv: exploratory low-EF operating points

Multiple recordings from one exam are aggregated by median before evaluation.
The command stops on exam or patient fold leakage. Missing-GT rows remain in
the inference CSV but do not enter accuracy metrics.

## Bias analysis order

1. Review every false negative in exam_predictions.csv.
2. Compare endpoint confidence, LVID ratio, ED/ES frames and source metadata.
3. Separate image/measurement failures from EF-calibration failures.
4. Compare group_metrics.csv across site and vendor.
5. Treat small-N subgroup differences as descriptive rather than established
   statistical disparities.

The threshold sweep uses the evaluation cohort and is exploratory. Select a new
operating threshold inside an inner validation split and freeze it before the
final test.
