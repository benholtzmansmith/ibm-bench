#!/usr/bin/env bash
# Run the airline evaluations against the active orchestrate environment.
# Usage: scripts/run_evals.sh [smoke|full] [local|remote]
#   smoke (default) runs 5 tasks, full runs all 50.
#   local (default) targets the server from setup_local.sh; remote targets the
#   instance from setup_remote.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SUITE="${1:-smoke}"
TARGET="${2:-local}"

if [[ "$TARGET" == "local" ]]; then
  orchestrate env activate local
  # The simulated user and judge reach the virtual model through the local gateway.
  unset WO_INSTANCE WO_API_KEY
else
  ENV_FILE="${ENV_FILE:-$ROOT/.env}"
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  # The eval gateway provider reads WO_INSTANCE and WO_API_KEY to call the
  # instance's AI gateway; the active environment from setup_remote.sh is used
  # for the agent itself.
  : "${WO_INSTANCE:?set WO_INSTANCE in $ENV_FILE}"
  : "${WO_API_KEY:?set WO_API_KEY in $ENV_FILE}"
  export WO_INSTANCE WO_API_KEY
fi

orchestrate evaluations evaluate -c "airline/evaluations/config.$SUITE.yaml" -o "results/$SUITE-$TARGET"
