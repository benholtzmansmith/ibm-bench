#!/usr/bin/env bash
# Start a local watsonx Orchestrate Developer Edition server, register the
# virtual model, and import the benchmark tools and agents.
# To use a SaaS instance instead, see setup_remote.sh.
#
# Usage: scripts/setup_local.sh [airline|retail]   (default: airline)
#   The two benchmarks share tool names (calculate, get_user_details,
#   transfer_to_human_agents) with different behavior, so an environment holds
#   one benchmark at a time. Re-run with the other name to switch.
#
# Reads .env in the repo root (copy .env.example and fill it in). It is passed
# to `orchestrate server start --env-file` and must set:
#   WO_ENTITLEMENT_KEY  IBM entitlement key, used to pull the Developer Edition images
#   ANTHROPIC_API_KEY   key behind the virtual model
# Optional, from the environment:
#   WO_CERT_BUNDLE      CA bundle for the containers, for networks behind a TLS-inspecting proxy
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
: "${WO_ENTITLEMENT_KEY:?set WO_ENTITLEMENT_KEY in $ENV_FILE}"
: "${ANTHROPIC_API_KEY:?set ANTHROPIC_API_KEY in $ENV_FILE}"

START_ARGS=(--env-file "$ENV_FILE" --accept-terms-and-conditions)
if [[ -n "${WO_CERT_BUNDLE:-}" ]]; then
  START_ARGS+=(--cert-bundle-path "$WO_CERT_BUNDLE")
fi
orchestrate server start "${START_ARGS[@]}"
orchestrate env activate local

scripts/import_"${1:-airline}".sh
