# Loading test cases into an Orchestrate instance

Status on 2026-10-07: **no working API route for storing test cases was found** on the trial instance (AWS-hosted SaaS, `mcsp_v2` auth). IBM documents such a route, but the instance answers 404 for it. The ADK and the evaluation framework don't store test cases in an instance at all. They read JSON files from disk and only call the instance to chat with the agent.

This page records what exists, what was tried, and the commands, so the check can be repeated on another instance or after an IBM update.

## Getting a token

`WO_INSTANCE` and `WO_API_KEY` come from the instance's Settings > API details page. On an MCSP v2 instance the key is exchanged for a bearer token at IBM's account IAM:

```bash
set -a; source .env; set +a
TOKEN=$(curl -s -X POST https://account-iam.platform.saas.ibm.com/api/2.0/apikeys/token \
  -H 'Content-Type: application/json' \
  -d "{\"apikey\": \"$WO_API_KEY\"}" | python3 -c 'import sys,json; print(json.load(sys.stdin)["token"])')
```

The token lasts about two hours. Find the agent id:

```bash
curl -s "$WO_INSTANCE/v1/orchestrate/agents" -H "Authorization: Bearer $TOKEN" \
  | python3 -c 'import sys,json; [print(a["id"], a["name"]) for a in json.load(sys.stdin)]'
AGENT_ID=<id of tau_airline_agent>
```

## What IBM documents

IBM's public server spec ([server_openapi.json](https://developer.watson-orchestrate.ibm.com/apis/server_openapi.json), "WxO Server API" 0.1.0, tag "Agent Evaluation") lists these routes:

| Method | Path | Purpose |
|---|---|---|
| GET | `/v1/orchestrate/agent/test_case/templates` | Sample test-case CSV file |
| POST | `/v1/orchestrate/agent/{agent_id}/test_case` | Upload test cases. `multipart/form-data` with one `file` field. Returns `test_case_ids` and `total_test_cases` |
| GET | `/v1/orchestrate/agent/{agent_id}/test_case` | List test cases (`query`, `limit`, `offset`, `sortkey`, `sort`). Each has `id`, `prompt`, `created_date`, `executed_date` |
| POST | `/v1/orchestrate/agent/{agent_id}/test_case/bulk_delete` | Delete test cases by id |
| POST | `/v1/orchestrate/agent/{agent_id}/evaluate` | Run test cases. Body `{"test_case_ids": [...]}`. Returns `evaluation_id` |
| GET | `/v1/orchestrate/agent/{agent_id}/evaluations` | List evaluations |
| GET | `/v1/orchestrate/agent/{agent_id}/evaluations/status` | Whether an evaluation is running |
| GET | `/v1/orchestrate/agent/{agent_id}/evaluations/{evaluation_id}` | Evaluation details and aggregate metrics |
| GET | `/v1/orchestrate/agent/{agent_id}/evaluations/{evaluation_id}/test_cases` | Per-test-case status (`IN_PROGRESS`, `PASSED`, `FAILED`) |
| POST | `/v1/orchestrate/agent/{agent_id}/evaluations/export` | Download evaluations |
| POST | `/v1/orchestrate/agent/{agent_id}/evaluations/bulk_delete` | Delete evaluations |

The documented test case is a prompt-style record uploaded as a CSV file. The spec doesn't give the CSV columns; the template route is meant to supply them. That's a different format from the ADK test-case JSON in `airline/evaluations/test_cases/`, which has a story, goals and expected tool calls.

IBM's product docs ([Managing test cases](https://www.ibm.com/docs/en/SSAVQO/agent_builder/Evaluation/record_manage_test_cases.html)) describe the UI side: an agent's Tests tab, where test cases are recorded from preview chat. They can be multi-turn, capture tool calls with Exact, Fuzzy or Ignored matching, and be edited as JSON.

## What the trial instance actually serves

Every request used a valid bearer token that works on other routes.

| Request | Result |
|---|---|
| `GET /v1/orchestrate/agent/{agent_id}/evaluations/status` | 200 `{"is_running":false,"evaluation_id":null}` |
| `GET /v1/orchestrate/agent/{agent_id}/evaluations/{evaluation_id}` | Route served: 404 `{"detail":"Evaluation not found"}` for an unknown id, 422 for a non-UUID |
| `GET /v1/orchestrate/evaluation/metrics` | 200 `{"metrics":[],"total":0,"page":1,"page_size":50,"total_pages":0}` (not in IBM's public spec) |
| `POST /v1/orchestrate/evaluation/metrics` with `{}` | 422, requires `name` and `definition` (custom metric; nothing was created) |
| `GET /v1/orchestrate/agent/{agent_id}/evaluations/export` | 403 `WXO-PROXY-13012E` Access denied |
| `GET /v1/orchestrate/agent/test_case/templates` | 404 `WXO-PROXY-14009E` |
| `GET /v1/orchestrate/agent/{agent_id}/test_case` (with and without `limit`/`offset`) | 404 `WXO-PROXY-14009E` |
| `POST /v1/orchestrate/agent/{agent_id}/test_case` (multipart `file`: txt, csv, json) | 404 `WXO-PROXY-14009E` |
| `POST /v1/orchestrate/agent/{agent_id}/evaluate` with `{}` | 404 `WXO-PROXY-14009E` |
| `GET /v1/orchestrate/agent/{agent_id}/evaluations` | 404 `WXO-PROXY-14009E` |
| `GET /v1/orchestrate/agent/{agent_id}/evaluations/{evaluation_id}/test_cases` | 404 `WXO-PROXY-14009E` |

`WXO-PROXY-14009E` ("The requested resource does not exist") comes from the instance's API proxy, before the request reaches the server. Routes that reach the server answer in a different shape (`{"detail": ...}`). So the test-case upload, list and run routes aren't exposed through the API endpoint on this instance.

Also tried, all 404 from the proxy:

- No API description at `/openapi.json`, `/v1/openapi.json`, `/docs`, `/redoc`, `/swagger.json`, `/api/v1/openapi.json` or `/v1/orchestrate/openapi.json`.
- About 750 read-only guesses at other names (`test_cases`, `tests`, `testcases`, `test-cases`, `datasets`, `test_suites`, `recordings`, `runs`) under `/v1/orchestrate`, `/v1/orchestrate/evaluation`, `/v1/orchestrate/agent/{id}` and `/v1/orchestrate/agents/{id}`. Only the routes in the table above answered.
- `/v2/orchestrate/...` returns a generic 500 for every path, so it tells us nothing.

Not checked: the bulk-delete routes (they only delete), and whatever routes the web UI's Tests tab calls with a browser session.

## Commands to repeat the check

```bash
# Served today
curl -s "$WO_INSTANCE/v1/orchestrate/agent/$AGENT_ID/evaluations/status" -H "Authorization: Bearer $TOKEN"
curl -s "$WO_INSTANCE/v1/orchestrate/evaluation/metrics" -H "Authorization: Bearer $TOKEN"

# Documented, 404 today. If these start returning 200, loading works:
curl -s "$WO_INSTANCE/v1/orchestrate/agent/test_case/templates" -H "Authorization: Bearer $TOKEN" -o template.csv
curl -s "$WO_INSTANCE/v1/orchestrate/agent/$AGENT_ID/test_case?limit=10&offset=0" -H "Authorization: Bearer $TOKEN"
curl -s -X POST "$WO_INSTANCE/v1/orchestrate/agent/$AGENT_ID/test_case" \
  -H "Authorization: Bearer $TOKEN" -F "file=@test_cases.csv"
curl -s -X POST "$WO_INSTANCE/v1/orchestrate/agent/$AGENT_ID/evaluate" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"test_case_ids": ["<id>"]}'
curl -s "$WO_INSTANCE/v1/orchestrate/agent/$AGENT_ID/evaluations/<evaluation_id>" -H "Authorization: Bearer $TOKEN"
```

## How test cases are used today

- The ADK (`orchestrate evaluations evaluate`) and the evaluation framework (`python -m agentops.main`) read test-case JSON from disk. Against the instance they call only the chat runs API and the AI gateway, and nothing is stored in the instance. See `scripts/run_evals.sh`.
- In the instance, test cases are created in the web UI: open the agent in Agent Builder, use the Tests tab, record a preview-chat conversation as a test case, and edit it with Modify JSON.

## Open questions

- Which routes the web UI's Tests tab calls. Opening that tab with the browser's network panel would show them, and whether they accept an API-key token.
- Whether the documented routes are served on other plans or regions, or on a local Developer Edition server.
- The format the UI accepts in Modify JSON, and whether an ADK test case can be pasted in after conversion.
