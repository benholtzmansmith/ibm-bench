#!/usr/bin/env bash
# Start a local watsonx Orchestrate Developer Edition server, register the
# virtual model, and import the tau-bench airline tools and agent.
#
# Required environment variables (never commit these):
#   WO_ENTITLEMENT_KEY  IBM entitlement key, used to pull the Developer Edition images
#   ANTHROPIC_API_KEY   key behind the virtual model
# Optional:
#   GROQ_API_KEY / WATSONX_APIKEY + WATSONX_SPACE_ID
#                       Developer Edition refuses to start without one of these.
#                       The airline agent never uses them, so a placeholder is set
#                       when none is provided.
#   WO_CERT_BUNDLE      CA bundle for the containers, for networks behind a TLS-inspecting proxy
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

: "${WO_ENTITLEMENT_KEY:?set WO_ENTITLEMENT_KEY}"
: "${ANTHROPIC_API_KEY:?set ANTHROPIC_API_KEY}"

ENV_FILE="$(mktemp)"
trap 'rm -f "$ENV_FILE"' EXIT
{
  echo "WO_DEVELOPER_EDITION_SOURCE=myibm"
  echo "WO_ENTITLEMENT_KEY=$WO_ENTITLEMENT_KEY"
  if [[ -n "${WATSONX_APIKEY:-}" ]]; then
    echo "WATSONX_APIKEY=$WATSONX_APIKEY"
    echo "WATSONX_SPACE_ID=${WATSONX_SPACE_ID:?set WATSONX_SPACE_ID with WATSONX_APIKEY}"
  else
    echo "GROQ_API_KEY=${GROQ_API_KEY:-unused-placeholder}"
  fi
} > "$ENV_FILE"

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
