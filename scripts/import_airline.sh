#!/usr/bin/env bash
# Import the virtual model, tools and agent into the active orchestrate environment.
# Needs ANTHROPIC_API_KEY in the environment. Safe to re-run: imports update in place.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

: "${ANTHROPIC_API_KEY:?set ANTHROPIC_API_KEY}"

# Virtual model: a key_value connection holds the provider key, the model points at it.
orchestrate connections add -a anthropic_creds || true
for env in draft live; do
  orchestrate connections configure -a anthropic_creds --env "$env" --type team --kind key_value
  orchestrate connections set-credentials -a anthropic_creds --env "$env" -e "api_key=$ANTHROPIC_API_KEY"
done
orchestrate models import -f airline/models/claude_sonnet.yaml --app-id anthropic_creds

orchestrate tools import -k python -f airline/tools/airline_tools.py \
  -r airline/tools/requirements.txt -p airline/tools
orchestrate agents import -f airline/agents/tau_airline_agent.yaml

orchestrate models list
orchestrate agents list
