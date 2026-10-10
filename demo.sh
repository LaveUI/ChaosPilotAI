#!/usr/bin/env bash
# Full loop: map -> baseline -> plan -> run -> fix -> rerun.
#   ./demo.sh          real cluster (needs the port-forward running)
#   ./demo.sh --sim    offline simulator, finishes in seconds
set -euo pipefail
SIM="${1:-}"
c() { python3 -m chaosai $SIM "$@"; }

c map
c baseline --seconds "${BASELINE_SECONDS:-30}"
c plan --n 3
c run
c fix
c rerun
echo
echo "Open the newest runs/*/report.html (before/after comparison is in the second one)."
