from __future__ import annotations

import argparse
import json
from pathlib import Path

from ...evaluation.lvef_dataset import evaluate_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate paired research LVEF predictions at exam level")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--low-ef-definition", type=float, default=40.0)
    parser.add_argument("--alert-ef-threshold", type=float, default=40.0)
    parser.add_argument("--probability-threshold", type=float, default=0.5)
    parser.add_argument("--group-columns", default="label_source,site,vendor,sex,age_group")
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260917)
    parser.add_argument("--require-patient-id", action="store_true")
    args = parser.parse_args()
    result = evaluate_manifest(
        args.manifest, args.output_dir, args.low_ef_definition, args.alert_ef_threshold,
        args.probability_threshold,
        [x.strip() for x in args.group_columns.split(",") if x.strip()],
        args.bootstrap, args.seed, args.require_patient_id,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
