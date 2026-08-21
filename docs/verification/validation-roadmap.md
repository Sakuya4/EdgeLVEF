# Validation roadmap

The next work is divided by evidence source. Board testing, external-dataset
evaluation, and expert review answer different questions and must not be merged
into one vague validation result.

## Track A: physical-board verification

**Owner:** the person holding the Embedded Linux board.

**Purpose:** determine whether the frozen Student Model executes correctly on
the intended hardware and runtime.

**Actions:**

1. clone the recorded Git commit;
2. run repository tests and both SHA-256 checks;
3. run the CPU baseline benchmark;
4. run an NPU provider only if the runtime exposes and confirms it;
5. analyze several de-identified full-cycle PLAX cines;
6. render overlays and record wall/ED/ES failures.

**Return:** benchmark JSON, functional-cine JSON, environment versions, active
provider, and visual findings. Do not return patient media unless governance
permits it.

## Track B: frozen external comparison

**Owner:** the model/research team after approved MIMIC-IV-ECHO access.

**Purpose:** compare the Student Model and Gao PLAX-EF Teacher on the same adult
PLAX studies without retuning either method.

**Actions:**

1. obtain credentialed MIMIC-IV-ECHO pixels under the DUA;
2. keep the Student Model, frozen head, preprocessing, and threshold unchanged;
3. run Student and Gao predictions on identical eligible cines;
4. aggregate multiple cines by study median;
5. report MAE, RMSE, bias, Bland--Altman limits, AUROC, AUPRC, sensitivity,
   specificity, PPV, NPV, and study-level bootstrap intervals;
6. retain every missing, corrupt, or failed cine in the accounting table.

**Return:** cohort flow, per-study predictions, paired metrics, confidence
intervals, and failure manifest. External cases are evaluation-only and cannot
become a new tuning set.

## Track C: blinded image audit

**Owner:** at least one reviewer who can recognize PLAX anatomy; two independent
reviewers are preferred.

**Purpose:** determine whether the Student Model tracks the intended opposing LV
walls and selects plausible ED/ES frames, rather than merely producing a useful
ranking score.

**Actions:**

1. provide blinded overlay videos without LVEF or low-EF labels;
2. rate PLAX compatibility, both wall paths, ED, ES, and overall usability;
3. lock the forms before opening the private case key;
4. report item-level acceptance with exact confidence intervals;
5. report Cohen kappa when two reviewers are available.

**Return:** locked rating forms and summary JSON. Operator or AI ratings cannot
be presented as an expert clinical audit.

## Integration gate

After all three tracks return, update the model card with separate subsections:

- hardware feasibility;
- external predictive performance;
- anatomical/phase audit.

Only then decide whether the evidence supports an engineering journal paper or
whether additional low-EF and multi-device data are required. Do not retrain in
response to any validation result until the complete frozen report is archived.
