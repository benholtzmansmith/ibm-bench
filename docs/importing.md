# Importing agents and tools

`scripts/import_airline.sh` and `scripts/import_retail.sh` run these commands for you. This page lists them so you can run one step on its own, for example to re-import only the tools after editing them.

Every command acts on the active orchestrate environment. Check which one that is first:

```bash
orchestrate env list                         # the active one is marked
orchestrate env activate local               # Developer Edition
orchestrate env activate trial --api-key "$WO_API_KEY"   # a SaaS instance added with `orchestrate env add`
```

Run the commands from the repo root with the venv active. Imports update in place, so re-running them is safe.

## 1. Model connection (only for the Claude virtual model)

The agent YAMLs use `virtual-model/anthropic/claude-sonnet-5-5`, which the AI gateway serves with an Anthropic key held in a `key_value` connection. Skip this step if the agent will use one of the instance's own models (see [Using an instance model](#using-an-instance-model)).

```bash
orchestrate connections add -a anthropic_creds
for env in draft live; do
  orchestrate connections configure -a anthropic_creds --env "$env" --type team --kind key_value
  orchestrate connections set-credentials -a anthropic_creds --env "$env" -e "api_key=$ANTHROPIC_API_KEY"
done
orchestrate models import -f airline/models/claude_sonnet.yaml --app-id anthropic_creds
```

`retail/models/claude_sonnet.yaml` registers the same model, so either file works.

## 2. Tools

Each benchmark's tools are one Python file. `-p` uploads the whole `tools/` folder so the tools can read the logic module and the database next to them, and `-r` installs their requirements.

```bash
# airline: 14 tools
orchestrate tools import -k python -f airline/tools/airline_tools.py \
  -r airline/tools/requirements.txt -p airline/tools

# retail: 16 tools
orchestrate tools import -k python -f retail/tools/retail_tools.py \
  -r retail/tools/requirements.txt -p retail/tools
```

The two benchmarks share three tool names (`calculate`, `get_user_details`, `transfer_to_human_agents`) with different behavior, so an environment holds one benchmark's tools at a time. Importing one set replaces those three tools from the other.

## 3. Agent

Import the agent after its tools, because the import checks that every tool it lists exists.

```bash
orchestrate agents import -f airline/agents/tau_airline_agent.yaml   # tau_airline_agent
orchestrate agents import -f retail/agents/tau2_retail_agent.yaml    # tau2_retail_agent
```

## Check what was imported

```bash
orchestrate models list
orchestrate tools list
orchestrate agents list
```

## Using an instance model

Without an Anthropic key, the agent can run on a model the instance already has (`orchestrate models list`). Either pick it in the Orchestrate UI after importing, or change `llm` in the agent YAML before importing, for example `llm: watsonx-orchestrate/frontier`.

Importing the agent YAML again resets `llm` to whatever the file says, so a model picked in the UI is lost on re-import. To update only the tools, run step 2 alone.

For evaluations with an instance model, see `EVAL_MODEL` in the [README](../README.md#running-against-a-watsonx-orchestrate-instance).
