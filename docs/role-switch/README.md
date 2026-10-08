# Simulated user switches role

In every run below, the evaluation framework's simulated user starts speaking as the airline agent partway through the conversation, and sometimes from its first turn. It asks the agent for a user ID, repeats the agent's refusals back to it, and in some tasks writes a fake tool call as its own message.

This folder holds the message history and the effective config for each run, so the behaviour can be reproduced or reported.

## Fix: the v2 simulator and universal prompt

The repo's eval configs now set `llm_user_config.version: v2`. That switches to the framework's v2 simulated user, which uses `agentops/prompt/universal_user_template.jinja2` (shipped in both framework 1.5.2 and 1.6.6). The v1 prompt pastes the conversation into one prompt as tagged turns and asks the model to continue it, so the model easily continues as the wrong speaker. The universal prompt is a system prompt with an explicit rule never to answer in the assistant's voice.

The same airline smoke suite on framework 1.6.6, everything else as below, on 2026-10-07:

| Simulated user | `enable_structured_output` | User turns | Turns that break role | Journey success |
|---|---|---|---|---|
| v1, default prompt | true | 47 | 29 (2 fake tool calls) | 0.60 |
| v2, universal prompt | true | 22 | 0 | 0.60 |
| v2, universal prompt | false | 29 | 0 | 0.80 |

Role breaks were counted by reading every simulated-user turn. With the v2 simulator, task 013 still fails because the agent refuses and never calls `transfer_to_human_agents`. Task 016 passed only in the run where the simulated user kept pushing, so its result depends on the user's persistence. One run per setting can't separate that from run-to-run variation.

To reproduce the runs below, set `version: v1` under `llm_user_config`.

## Setup common to all runs

- Target: a watsonx Orchestrate trial instance (AWS-hosted SaaS), run on 2026-10-07.
- Agent under test: `tau_airline_agent` with its model set to `watsonx-orchestrate/frontier` in the instance.
- Simulated user and judge: `watsonx-orchestrate/frontier` through the instance's AI gateway (`provider: gateway`).
- Simulated-user prompt: the framework default, `agentops/prompt/gpt/gpt_user_template_v1.jinja2`, `version: v1`.
- Environment: `GATEWAY_MODEL_PREFIX=""`. Without it the framework sends `watsonx/watsonx-orchestrate/frontier` and the gateway returns 404.
- Test cases: the five in `airline/evaluations/config.smoke.yaml`.

## Runs

| Folder | Runner | `enable_structured_output` | Tasks |
|---|---|---|---|
| `adk-2.18.0-smoke/` | `orchestrate evaluations evaluate` (ADK 2.18.0, framework 1.5.2) | false | 001, 013, 016, 043, 044 |
| `adk-2.18.0-structured-013/` | same | true | 013 |
| `framework-1.6.6-structured-013/` | `python -m agentops.main` (framework 1.6.6) | true | 013 |
| `framework-1.6.6-structured-smoke/` | same | true | 001, 013, 016, 043, 044 |

Each folder contains:

- `config.yml`: the effective config the run saved. The token is removed, and the instance URL and local paths are replaced with placeholders.
- `summary_metrics.csv`: per-task scores.
- `messages/<task>.messages.json`: the full message history. Entries with `"role": "user"` are the simulated user.

## Where the switch happens

The numbers are zero-based indexes into the `messages.json` array. Each listed entry has `"role": "user"` but reads as an agent turn. They were identified by reading the turns, not by an automated check.

### `adk-2.18.0-smoke` (structured output off)

| Task | Simulated-user turns in the agent's voice | Example |
|---|---|---|
| 001 | 0, 4, 6, 12, 21, 23, 28, 30, 32, 38 | [0] "Hello! How can I assist you today?" |
| 013 | 9, 14, 18 | [9] "Of course! What change would you like to make to your reservation XEWRD9?" |
| 016 | 3, 9, 29, 34, 36, 38, 42, 44 | [3] "Of course! To get started, could you please provide me with your **user ID**" |
| 043 | 2, 13, 15 | [2] "Sure! Could you please provide me with your user ID so I can locate your account" |
| 044 | 7 | [7] "Of course! To confirm your total baggage allowance in numeric form:" |

Fake tool calls written by the simulated user: 001 [28] `cancel_reservation`, 016 [9] `get_reservation_details`, 043 [13] `update_reservation_passengers`.

### `adk-2.18.0-structured-013` (structured output on)

| Task | Simulated-user turns in the agent's voice | Example |
|---|---|---|
| 013 | 9, 14 | [14] "I understand you'd like to make this change, but unfortunately I'm unable to process it" |

### `framework-1.6.6-structured-013` (structured output on)

| Task | Simulated-user turns in the agent's voice | Example |
|---|---|---|
| 013 | 7 | [7] "Sure! I'd like to help you with your reservation. Could you please let me know specifically what change you'd like to make?" |

### `framework-1.6.6-structured-smoke` (structured output on)

| Task | Simulated-user turns in the agent's voice | Example |
|---|---|---|
| 001 | 0, 4, 6, 12, 21, 23, 25, 30, 32, 38 | [0] "Hello! How can I assist you today?" |
| 013 | 9, 13 | [13] "Is there anything else I can help you with from the available options for your reservation?" |
| 016 | 29, 34, 36, 38, 42 | [38] "I appreciate your patience, Ethan. To move forward, I need a clear answer from you:" |
| 043 | 2, 10, 14, 16, 20, 22 | [14] "I'm sorry, but I'm unable to process this name change." |
| 044 | 3, 12, 14, 16, 18, 20 | [3] "Sure! Could you please provide me with your user ID so I can look up your account" |

Fake tool calls written by the simulated user: 001 [30] `cancel_reservation`, 043 [22] `update_reservation_passenger` (a tool name that does not exist).

## What it does to the scores

Journey success was 3 of 5 in both smoke runs (001, 043 and 044 pass; 013 and 016 fail).

- The passing tasks pass despite the switch, because the agent still makes the expected calls.
- 013 expects `transfer_to_human_agents` and 016 expects `send_certificate`. In both, the agent refuses the request and the simulated user then echoes the refusal instead of pressing, so the conversation ends. The agent also never transfers on its own in 013, so the failures are not only the simulator's.
- Tool-call precision is low everywhere (0.28 average) for a separate reason: any call outside the expected list counts as wrong, including lookups and `think`.

## What was tried

- `enable_structured_output: true` under `llm_user_config`: the setting reached the run (see `config.yml`) and did not stop the switch.
- Framework 1.6.6 instead of the 1.5.2 bundled with ADK 2.18.0: no change.

Not yet tried: a different model for the simulated user (the instance also lists `groq/openai/gpt-oss-120b` and `bedrock/openai.gpt-oss-120b-1:0`), or `llm_user_config.version: v2`.

## Reproducing

ADK runner, from the repo root with the trial environment active and `WO_INSTANCE` / `WO_API_KEY` exported from `.env`:

```bash
mkdir -p results
sed 's#virtual-model/anthropic/claude-sonnet-5-5#watsonx-orchestrate/frontier#' \
  airline/evaluations/config.smoke.yaml > results/config.smoke.remote.yaml
GATEWAY_MODEL_PREFIX="" orchestrate evaluations evaluate \
  -c results/config.smoke.remote.yaml -o results/smoke-remote
```

Framework 1.6.6 directly, from a separate venv with `ibm-watsonx-orchestrate-evaluation-framework==1.6.6`:

```bash
GATEWAY_MODEL_PREFIX="" python -m agentops.main \
  --config results/config.smoke.remote.yaml \
  --auth_config.url "$WO_INSTANCE" --auth_config.tenant_name trial \
  --output_dir results/evalfw-smoke --is_adk true --skip_legacy_evaluation true
```

Add `enable_structured_output: true` under `llm_user_config` in the config for the structured-output runs. To run one task, add `-p airline/evaluations/test_cases/airline_task_013.json` to the ADK command, or `--test_paths '["airline/evaluations/test_cases/airline_task_013.json"]'` to the framework command.
