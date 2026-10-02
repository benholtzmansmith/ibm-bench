#!/usr/bin/env bash
# Start a local watsonx Orchestrate Developer Edition server, register the
# virtual model, and import the tau-bench airline tools and agent.
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

# Virtual model: a key_value connection holds the provider key, the model points at it.
orchestrate connections add -a anthropic_creds || true
orchestrate connections configure -a anthropic_creds --env draft --type team --kind key_value
orchestrate connections set-credentials -a anthropic_creds --env draft -e "api_key=$ANTHROPIC_API_KEY"
orchestrate models import -f airline/models/claude_sonnet.yaml --app-id anthropic_creds

orchestrate tools import -k python -f airline/tools/airline_tools.py \
  -r airline/tools/requirements.txt -p airline/tools
orchestrate agents import -f airline/agents/tau_airline_agent.yaml

orchestrate models list
orchestrate agents list
