# ibm-bench

Agent benchmarks packaged for IBM watsonx Orchestrate, written in the
[watsonx Orchestrate ADK](https://developer.watson-orchestrate.ibm.com/) formats
for agents, tools, models and evaluations.

| Benchmark | Source | What's here |
|---|---|---|
| [`airline/`](airline/) | [tau-bench](https://github.com/sierra-research/tau-bench) airline domain (`59a200c`) | 1 agent, 14 Python tools, the tau-bench database, 50 evaluation test cases |
| [`retail/`](retail/) | [tau2-bench](https://github.com/sierra-research/tau2-bench) retail domain (`4ce7c03`) | 1 agent, 16 Python tools, the tau2 database, 114 evaluation test cases (tau2's `base` split) |

## Layout

```
airline/
  agents/tau_airline_agent.yaml     ADK native agent; instructions are tau-bench's airline policy
  tools/airline_tools.py            ADK @tool wrappers, same names and arguments as tau-bench
  tools/airline_logic.py            tau-bench tool logic, ported verbatim
  tools/data/*.json                 tau-bench flights, reservations and users
  models/claude_sonnet.yaml         virtual model spec for the AI gateway
  evaluations/test_cases/*.json     ADK test cases, one per tau-bench test task
  evaluations/config.{smoke,full}.yaml
  source/                           tau-bench tasks (as JSON), policy and license
retail/
  agents/tau2_retail_agent.yaml     ADK native agent; instructions are tau2's retail policy
  tools/retail_tools.py             ADK @tool wrappers, same names and arguments as tau2
  tools/retail_logic.py             tau2 data model and tool logic, ported verbatim
  tools/data/db.json                tau2 products, users and orders
  models/claude_sonnet.yaml         virtual model spec for the AI gateway
  evaluations/test_cases/*.json     ADK test cases, one per tau2 task
  evaluations/config.{smoke,full}.yaml
  source/                           tau2 tasks, splits, policy and license
scripts/
  convert_tau_tasks.py              regenerates the airline test cases from airline/source/tasks_test.json
  convert_tau2_retail_tasks.py      regenerates the retail test cases from retail/source/tasks.json
  setup_local.sh [airline|retail]   starts Developer Edition, then runs import_<benchmark>.sh
  setup_remote.sh [airline|retail]  activates a SaaS instance (e.g. a trial), then runs import_<benchmark>.sh
  import_{airline,retail}.sh        adds the virtual model, tools and agent to the active environment
  run_evals.sh                      runs a benchmark's smoke (5 tasks) or full suite
tests/                              offline checks, no server needed
docs/
  importing-agents-and-tools.md     ADK commands for importing tools, agents and the model, step by step
  role-switch/                      message history and configs for runs where the simulated user speaks as the agent
```

## How tau-bench maps onto the ADK

| tau-bench | ADK |
|---|---|
| `wiki.md` system prompt | agent `instructions` |
| `Tool.invoke` / `get_info` | `@tool` Python functions with the same names, arguments and descriptions |
| task `instruction` | test case `story`, played by the ADK LLM user simulator |
| task `actions` | `tool_call` goals with tau-bench's exact arguments; writes stay in tau-bench's order and the reads before each write are unordered |
| task `outputs` | `keywords` on the final `summarize` goal |
| final-database-hash reward | not reproduced; the ADK scores tool calls and the final response instead |

Two behaviors differ from tau-bench:

- **Tool state does not carry across calls.** Orchestrate runs each tool call in a fresh process, so every call starts from the original database. Writes are validated and return the same result as tau-bench, but a later read in the same conversation will not see them.
- **Scoring is per tool call, not per final state.** A run passes when the expected calls are made with matching arguments. `calculate.expression` and `think.thought` are ignored, and `transfer_to_human_agents.summary` is fuzzy-matched.

## How tau2-bench retail maps onto the ADK

The retail port follows the airline mapping, with tau2's task format:

| tau2-bench | ADK |
|---|---|
| `policy.md` | agent `instructions` |
| `RetailTools` methods | `@tool` Python functions with the same names, arguments and descriptions; errors come back as `Error: ...` strings, as tau2's environment returns them |
| `user_scenario` | test case `story`, rendered with the same text tau2 gives its user simulator |
| `evaluation_criteria.actions` | `tool_call` goals in the same order scheme as airline; arguments outside `compare_args` are ignored |
| `communicate_info` | `keywords` on the final `summarize` goal |
| `nl_assertions` | appended to the expected final response the judge compares against |
| final-database-hash reward | not reproduced, as for airline |

The same two caveats apply: each tool call starts from the original database, and scoring is per tool call. The offline tests check that every gold action in all 114 tasks gives the same success or error against the original database as it does with state carried through the conversation, so the missing state changes some returned values (for example a gift card balance after an earlier payment change) but never whether a gold call succeeds. tau2 checks `communicate_info` against every agent message; the ADK checks keywords on the final response only.

The airline and retail agents share three tool names (`calculate`, `get_user_details`, `transfer_to_human_agents`) with different behavior, so an Orchestrate environment holds one benchmark at a time. `setup_*.sh retail` or `scripts/import_retail.sh` switches it to retail, and `scripts/import_airline.sh` switches it back.

## Offline checks

```bash
uv venv --python 3.12 && . .venv/bin/activate
uv pip install -r requirements-dev.txt
pytest
```

These tests check that the agent, tool and model specs load with the ADK and that every test case validates against the ADK schema and the tool signatures. They also replay the gold actions of all 50 airline and 114 retail tasks through the ports.

## Running against a local Orchestrate

Requires Docker and the venv above (so `orchestrate` is on your PATH). Put the keys in `.env`, which `orchestrate server start --env-file` reads:

```bash
cp .env.example .env        # then set WO_ENTITLEMENT_KEY and ANTHROPIC_API_KEY; .env is gitignored
scripts/setup_local.sh      # server start, connection + virtual model, airline tools + agent import
scripts/run_evals.sh smoke  # 5 airline tasks; use `full` for all 50
orchestrate evaluations analyze -d results/airline-smoke-local

scripts/import_retail.sh                # switch the server to the tau2 retail agent
scripts/run_evals.sh smoke local retail # 5 retail tasks; `full` runs all 114
orchestrate evaluations analyze -d results/retail-smoke-local
```

- `WO_ENTITLEMENT_KEY`: IBM entitlement key, used to pull the Developer Edition images from `cp.icr.io`.
- `ANTHROPIC_API_KEY`: the key behind the virtual model `virtual-model/anthropic/claude-sonnet-5-5`.

The agent, the simulated user and the judge all call the virtual model through the local AI gateway. Developer Edition refuses to start without a Groq or watsonx.ai credential even when nothing uses it, so `.env.example` sets a placeholder `GROQ_API_KEY`.

## Running against a watsonx Orchestrate instance

If Developer Edition can't pull its images (for example, IBM's registry rejects a trial instance's key), run the same agent and evals on a SaaS instance instead. Put `WO_INSTANCE` and `WO_API_KEY` from the instance's Settings → API details, plus `ANTHROPIC_API_KEY`, in `.env`:

```bash
scripts/setup_remote.sh             # env add + activate, connection + virtual model, airline tools + agent import
scripts/run_evals.sh smoke remote
orchestrate evaluations analyze -d results/airline-smoke-remote

scripts/setup_remote.sh retail      # same, with the tau2 retail tools and agent
scripts/run_evals.sh smoke remote retail
orchestrate evaluations analyze -d results/retail-smoke-remote
```

This creates the `anthropic_creds` connection, the virtual model, and the benchmark's tools and agent in that instance.

To try another model, add a spec under `<benchmark>/models/` and change `llm` in the agent YAML and `model_id` in the eval configs.

## License

The airline data, policy, tasks and tool logic come from tau-bench, © 2024 Sierra, under the MIT license (`airline/source/TAU_BENCH_LICENSE.txt`). The retail data, policy, tasks and tool logic come from tau2-bench, © 2025 Sierra Research, under the MIT license (`retail/source/TAU2_BENCH_LICENSE.txt`).
