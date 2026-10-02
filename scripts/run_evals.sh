#!/usr/bin/env bash
# Run the airline evaluations against the local server started by setup_local.sh.
# Usage: scripts/run_evals.sh [smoke|full]   (default: smoke, 5 tasks)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SUITE="${1:-smoke}"
orchestrate env activate local
orchestrate evaluations evaluate -c "airline/evaluations/config.$SUITE.yaml"
