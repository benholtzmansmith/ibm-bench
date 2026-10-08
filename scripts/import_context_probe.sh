#!/usr/bin/env bash
# Import the context persistence probe (virtual model, tools, agent) into the active
# orchestrate environment. Needs ANTHROPIC_API_KEY in the environment. Its tool
# names do not clash with the benchmarks, so it can sit next to either one.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

: "${ANTHROPIC_API_KEY:?set ANTHROPIC_API_KEY}"

orchestrate connections add -a anthropic_creds || true
for env in draft live; do
  orchestrate connections configure -a anthropic_creds --env "$env" --type team --kind key_value
  orchestrate connections set-credentials -a anthropic_creds --env "$env" -e "api_key=$ANTHROPIC_API_KEY"
done
orchestrate models import -f retail/models/claude_sonnet.yaml --app-id anthropic_creds

orchestrate tools import -k python -f context_probe/tools/probe_tools.py \
  -r context_probe/tools/requirements.txt -p context_probe/tools
orchestrate agents import -f context_probe/agents/context_probe_agent.yaml

orchestrate agents list
