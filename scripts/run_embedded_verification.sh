#!/usr/bin/env bash
set -euo pipefail

target_name="${1:-embedded-linux-board}"
provider="${2:-CPUExecutionProvider}"

python -m edgelvef.interfaces.cli.benchmark \
  --target-name "$target_name" \
  --provider "$provider" \
  --output "outputs/${target_name}-benchmark.json" \
  --warmup 20 \
  --runs 200 \
  --claim-physical-target
