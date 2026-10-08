# Importing agents and tools

Commands for getting the benchmark tools and agents into a watsonx Orchestrate environment with the ADK CLI. Run everything from the repo root with the venv active.

The scripts in `scripts/` wrap these commands. Use the commands directly when you want to import one piece, or when the environment has no Anthropic key.

## 1. Choose the environment

Imports go to whichever orchestrate environment is active.

Remote SaaS or trial instance (`WO_INSTANCE` and `WO_API_KEY` come from the instance's Settings > API details page):

```bash
set -a; source .env; set +a
orchestrate env add -n trial -u "$WO_INSTANCE" --type mcsp_v2   # once
orchestrate env activate trial --api-key "$WO_API_KEY"
```

`--type` is optional. Leave it off to let the ADK infer the auth type from the URL; `mcsp_v2` is what an AWS-hosted trial needed.

The token from `env activate` expires after about two hours. Run `env activate` again if a command returns an auth error.

Local Developer Edition server:

```bash
orchestrate env activate local
```

Check which one is active:

```bash
orchestrate env list
```

## 2. Import the tools

Tools go first, because the agent import resolves tool names against the environment.

Airline (14 tools):

```bash
orchestrate tools import -k python -f airline/tools/airline_tools.py \
  -r airline/tools/requirements.txt -p airline/tools
```

Retail:

```bash
orchestrate tools import -k python -f retail/tools/retail_tools.py \
  -r retail/tools/requirements.txt -p retail/tools
```

- `-k python` is the tool kind.
- `-f` is the file with the `@tool` functions.
- `-r` is the requirements file installed alongside the tools.
- `-p` is the package root, so the tools can import `*_logic.py` and read `data/`.

Re-running the command updates the tools in place.

## 3. Import the agent

Airline:

```bash
orchestrate agents import -f airline/agents/tau_airline_agent.yaml
```

Retail:

```bash
orchestrate agents import -f retail/agents/tau2_retail_agent.yaml
```

The import succeeds even when the agent's `llm` does not exist in the environment. The agent then fails at chat time until the model exists or you pick another one.

Importing again overwrites the agent with the YAML, including `llm`. If you changed the model in the Orchestrate UI, a re-import puts it back to `virtual-model/anthropic/claude-sonnet-5-5`.

The import prints a deprecation warning for `style: default` (the ADK suggests `react_core`). It is a warning only.

## 4. Give the agent a model

The agent YAMLs name `virtual-model/anthropic/claude-sonnet-5-5`. There are two ways to satisfy that.

Register the virtual model (needs `ANTHROPIC_API_KEY`):

```bash
orchestrate connections add -a anthropic_creds
for env in draft live; do
  orchestrate connections configure -a anthropic_creds --env "$env" --type team --kind key_value
  orchestrate connections set-credentials -a anthropic_creds --env "$env" -e "api_key=$ANTHROPIC_API_KEY"
done
orchestrate models import -f airline/models/claude_sonnet.yaml --app-id anthropic_creds
```

Or use a model the instance already has. List them, then either set the agent's model in the Orchestrate UI or change `llm:` in the agent YAML and import again:

```bash
orchestrate models list
```

A trial instance listed `watsonx-orchestrate/frontier`, `groq/openai/gpt-oss-120b` and `bedrock/openai.gpt-oss-120b-1:0`.

## 5. Verify

```bash
orchestrate tools list
orchestrate agents list
orchestrate agents list -v    # JSON, shows each agent's llm and attached tools
```

`tau_airline_agent` should show 14 tools.

## One-step scripts

| Script | What it does |
|---|---|
| `scripts/setup_remote.sh [airline\|retail]` | Reads `.env`, adds and activates the remote environment, then runs the benchmark's import script |
| `scripts/setup_local.sh [airline\|retail]` | Starts Developer Edition, then runs the benchmark's import script |
| `scripts/import_airline.sh` | Connection, virtual model, airline tools, airline agent into the active environment |
| `scripts/import_retail.sh` | Same for retail |

The import scripts stop early when `ANTHROPIC_API_KEY` is unset. Without that key, use steps 2 and 3 directly and pick an existing model in step 4.

To reuse an environment name other than the default `wxo-remote`:

```bash
WO_ENV_NAME=trial WO_ENV_TYPE=mcsp_v2 scripts/setup_remote.sh
```
