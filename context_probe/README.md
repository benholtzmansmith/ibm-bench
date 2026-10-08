# Context persistence probe

A three-tool agent that answers one question before we build stateful tau2 tools:
**does Orchestrate keep a Python tool's context updates for the rest of a conversation?**

Each tool takes an `AgentRun` parameter, which Orchestrate fills with the run's
context variables and hides from the LLM. `probe_remember_note` appends a note to
the `probe_notes` context variable; `probe_recall_notes` reads it back and prints
`PERSISTED_COUNT=<n> NOTES=...`; `probe_show_context` prints every context
variable the call received.

## Run it

From the repo root, with the remote environment from `scripts/setup_remote.sh` active:

```bash
set -a; source .env; set +a          # ANTHROPIC_API_KEY, WO_INSTANCE, WO_API_KEY
scripts/import_context_probe.sh      # 3 tools + context_probe_agent; no clash with airline/retail
scripts/run_evals.sh smoke remote context_probe
orchestrate evaluations analyze -d results/context_probe-smoke-remote
```

Or chat with `context_probe_agent` in the Orchestrate UI: ask it to remember
"alpha", then in a new message "beta", then ask which notes are stored.

## Reading the result

| Outcome | What it means |
|---|---|
| `PERSISTED_COUNT=2 NOTES=alpha,beta` | Context updates persist across turns. The tau2 tools can keep their database diff in context. |
| `PERSISTED_COUNT=1 NOTES=beta` on the recall, or `persisted_count_before_this_call` is 0 on the second note | Updates are dropped between turns (or only kept within one turn). We need the external state service. |
| `PERSISTED_COUNT=0` | Updates never come back to tools, or the context is filtered. Check `received_context` and the agent's `context_variables`. |

`context_probe_runtime` also checks that a test case's `runtime_context`
(`probe_session: case-42`) reaches tools, which is how a test case would seed or
label its database. The `received_context` field in every tool result shows
which other variables (for example a thread id) Orchestrate passes in.
