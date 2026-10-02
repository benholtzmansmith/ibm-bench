# ibm-bench

Agent benchmarks packaged for IBM watsonx Orchestrate, written in the
[watsonx Orchestrate ADK](https://developer.watson-orchestrate.ibm.com/) formats
for agents, tools, models and evaluations.

| Benchmark | Source | What's here |
|---|---|---|
| [`airline/`](airline/) | [tau-bench](https://github.com/sierra-research/tau-bench) airline domain (`59a200c`) | 1 agent, 14 Python tools, the tau-bench database, 50 evaluation test cases |

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
scripts/
  convert_tau_tasks.py              regenerates the test cases from source/tasks_test.json
  setup_local.sh                    starts Developer Edition, adds the virtual model, imports tools and agent
  run_evals.sh                      runs the smoke (5 tasks) or full (50 tasks) suite
tests/                              offline checks, no server needed
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

## Offline checks

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

These tests check that the agent, tool and model specs load with the ADK and that every test case validates against the ADK schema and the tool signatures. They also replay tau-bench's gold actions for all 50 tasks through the port.

## Running against a local Orchestrate

Requires Docker and these environment variables:

- `WO_ENTITLEMENT_KEY`: IBM entitlement key, used to pull the Developer Edition images from `cp.icr.io`.
- `ANTHROPIC_API_KEY`: the key behind the virtual model `virtual-model/anthropic/claude-sonnet-5-5`.

```bash
scripts/setup_local.sh      # server start, connection + virtual model, tools + agent import
scripts/run_evals.sh smoke  # 5 tasks; use `full` for all 50
orchestrate evaluations analyze -d results/smoke
```

The agent, the simulated user and the judge all call the virtual model through the local AI gateway. Developer Edition refuses to start without a Groq or watsonx.ai credential even when nothing uses it, so `setup_local.sh` sets a placeholder `GROQ_API_KEY` unless you provide a real one.

To try another model, add a spec under `airline/models/` and change `llm` in the agent YAML and `model_id` in the eval configs.

## License

The airline data, policy, tasks and tool logic come from tau-bench, © 2024 Sierra, under the MIT license (`airline/source/TAU_BENCH_LICENSE.txt`).
