#!/usr/bin/env bash
# Run a benchmark's evaluations against the active orchestrate environment.
# Usage: scripts/run_evals.sh [smoke|full] [local|remote] [airline|retail]
#   smoke (default) runs 5 tasks, full runs every task (50 airline, 114 retail).
#   local (default) targets the server from setup_local.sh; remote targets the
#   instance from setup_remote.sh.
#   airline (default) is the tau-bench airline port, retail the tau2-bench retail port.
# Optional environment:
#   EVAL_MODEL  model for the simulated user and the judge, overriding the config's
#               model_id (e.g. watsonx-orchestrate/frontier on a SaaS instance
#               that doesn't have the Claude virtual model)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SUITE="${1:-smoke}"
TARGET="${2:-local}"
BENCH="${3:-airline}"

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

# The eval library prefixes gateway model ids with "watsonx/" by default, which
# turns virtual-model/... and watsonx-orchestrate/... ids into 404s.
export GATEWAY_MODEL_PREFIX="${GATEWAY_MODEL_PREFIX-}"

CONFIG="$BENCH/evaluations/config.$SUITE.yaml"
if [[ -n "${EVAL_MODEL:-}" ]]; then
  TMP_CONFIG="$(mktemp "${TMPDIR:-/tmp}/eval-config.XXXXXX")"
  trap 'rm -f "$TMP_CONFIG"' EXIT
  sed -E "s#^([[:space:]]*model_id:).*#\1 $EVAL_MODEL#" "$CONFIG" > "$TMP_CONFIG"
  CONFIG="$TMP_CONFIG"
fi

orchestrate evaluations evaluate -c "$CONFIG" -o "results/$BENCH-$SUITE-$TARGET"
