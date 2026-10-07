#!/usr/bin/env bash
# Use a watsonx Orchestrate SaaS instance (for example a 30-day trial) instead of
# a local server: register it as an orchestrate environment, activate it, and
# import the virtual model, tools and agent into it.
#
# Reads .env in the repo root, which must set:
#   WO_INSTANCE        service instance URL (Settings > API details)
#   WO_API_KEY         API key from the same page
#   ANTHROPIC_API_KEY  key behind the virtual model
# Optional:
#   WO_ENV_NAME        orchestrate environment name (default: wxo-remote)
#   WO_ENV_TYPE        auth type for `orchestrate env add` (ibm_iam, mcsp, mcsp_v1, mcsp_v2, ...);
#                      the ADK infers it from WO_INSTANCE when unset
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${ENV_FILE:-$ROOT/.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE. Run: cp .env.example .env, then fill in the keys." >&2
  exit 1
fi
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
: "${WO_INSTANCE:?set WO_INSTANCE in $ENV_FILE}"
: "${WO_API_KEY:?set WO_API_KEY in $ENV_FILE}"
: "${ANTHROPIC_API_KEY:?set ANTHROPIC_API_KEY in $ENV_FILE}"

NAME="${WO_ENV_NAME:-wxo-remote}"
ADD_ARGS=(-n "$NAME" -u "$WO_INSTANCE")
if [[ -n "${WO_ENV_TYPE:-}" ]]; then
  ADD_ARGS+=(--type "$WO_ENV_TYPE")
fi
orchestrate env add "${ADD_ARGS[@]}" || true
orchestrate env activate "$NAME" --api-key "$WO_API_KEY"

scripts/import_airline.sh
