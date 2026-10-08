# Proposed metric: efficiency-adjusted goal completion

Status: proposal. Nothing in the repo computes this yet.

The ADK's `is_success` is all or nothing, and it does not care how many steps the agent took to get there. This proposal scores each run between 0 and 1, gives partial credit for the goals the agent did meet, and discounts runs that take more steps than the task needs.

## The score for one run

```
score = (goals met / goals listed) × d ^ (steps / goals listed)
```

- **goals listed**: the checks written for this task (see below). Every goal counts the same; there are no weights for now.
- **goals met**: how many of those checks pass.
- **steps**: the number of normalized steps the agent took in the run (see [What counts as a step](#what-counts-as-a-step)). For the agents in this repo, that is every tool call except `think`.
- **d = 0.98**: the discount per step.
- **Forbidden action**: if the agent does anything the task forbids, the score is 0, whatever else it got right.

The first factor answers "did it do the job". The second answers "did it do it efficiently". Dividing steps by goals listed keeps big tasks from being punished for needing more calls: a task with five goals is expected to take more steps than a task with one.

How hard d bites, as steps per goal grows:

| steps / goals listed | 1 | 2 | 3 | 5 | 10 | 20 |
|---|---|---|---|---|---|---|
| efficiency factor | 0.98 | 0.96 | 0.94 | 0.90 | 0.82 | 0.67 |

So an agent that meets every goal in a sensible number of calls scores in the mid to high 0.9s, and one that wanders for ten calls per goal loses about a fifth of its score. A lower d (say 0.95) makes efficiency matter more.

## Which goals a task lists

Each task lists only the goals that apply to it, chosen from four kinds:

| Goal kind | Listed when | Passes when |
|---|---|---|
| Correct end state | the task changes data (any write tool is expected) | the database after the run matches the expected database |
| Required tool call | the task needs a specific call | the call is made with matching arguments, one goal per call |
| Required info communicated | the user must be told something | the agent's messages contain it |
| No forbidden action | the task has an action the agent must not take | the agent never takes it |

Not every task needs a database check. A question-only task (for example, airline task 044, "what is my baggage allowance") lists no end-state goal and is scored on its tool calls and what the agent told the user. Two of the 114 retail tasks have no gold actions at all and are scored only on communication and forbidden actions.

"No forbidden action" is listed as a goal so the task's goal count is honest, but failing it does not just lose one goal: it zeroes the run.

## What counts as a step

Traces differ by agent type: a tool-calling agent logs function calls, a multi-agent system logs handoffs, a code agent logs executions, a browser agent logs clicks. To compare them, a step is defined by what it does, not by how the trace records it:

**A step is one action the agent chooses that reaches outside its own reasoning: it reads from or changes the environment, or hands work to another agent.**

| In the trace | Steps | Why |
|---|---|---|
| Tool or function call, read or write | 1 each | The basic unit of work. Parallel calls in one turn count once each, so batching doesn't hide work. |
| Failed or retried call | 1 each | A wasted call still cost time and money. |
| Reasoning-only tool (`think`, a scratchpad) | 0 | It doesn't touch the environment. It is the same as thinking in text, which isn't counted either. |
| Model reasoning, planning or thinking text | 0 | Internal. Measure it as tokens or cost if it matters. |
| Message to the user | 0 | The simulated user sets how many turns there are, and counting messages would punish asking a needed clarifying question. |
| Handoff to another agent (collaborator, sub-agent) | 1, plus every step the other agent takes | Delegating is an action, and the work doesn't become free because a different agent did it. |
| Code execution | 1 per execution | Each run is one action, however many lines it has. |
| Browser or GUI action (click, type, navigate) | 1 each | The atomic action of that interface. |
| Calls the framework makes on its own (routing, guardrails, retrieval it injects automatically) | 0 | The agent didn't choose them, so they say nothing about its efficiency. |

Two rules keep this consistent:

- **Count the gold trajectory the same way.** Where a task has a reference solution (tau's gold actions), its step count uses the same table, so "steps used" and "steps needed" are in the same unit. That is what the step budget below, or an SPL-style ratio, would compare against.
- **Write it down per agent type.** When a new kind of agent or trace format is added, list which of its trace events map onto which row above, before scoring it.

For the agents in this repo, steps = tool calls in `messages.json` minus `think` calls. Orchestrate's `total_tool_calls` includes `think`: in the airline smoke run, task 016 has 15 tool calls of which 4 are `think`, so it took 11 steps. `total_steps` counts every message and LLM step, so it isn't a step count in this sense.

## Reliability: report pass^k as well

The mean score says how good the average run is. It does not say whether the agent can be trusted to get it right every time. Report pass^k next to it, as tau-bench does:

- A run **passes** when it meets every goal (goals met = goals listed) and takes no forbidden action. Efficiency does not affect passing.
- For a task run n times with c passes, the chance that k random runs all pass is C(c, k) / C(n, k).
- pass^k is that number averaged over tasks. pass^1 is the plain pass rate.

A version that raises the mean score but lowers pass^3 is better on average and less dependable, and that is worth seeing.

## Comparing two agent versions

To decide whether version B is better than version A:

1. **Same setup.** Run both versions on the same tests, with the same simulated-user model and prompt, and the same n. Use n ≥ 3, because the simulated user is random and one run per test can't tell a real change from noise.
2. **Per-test score.** For each test, average the score over its n runs.
3. **Paired difference.** For each test, subtract A's score from B's. Report the mean of those differences, and a win/tie/loss count across tests (a tie is a difference of exactly 0, or within a small tolerance you pick up front).
4. **Is it real.** Bootstrap a 95% confidence interval on the mean difference: resample the tests with replacement (10,000 times is plenty), recompute the mean difference each time, and take the 2.5th and 97.5th percentiles. If the interval is entirely above 0, B is better. If it includes 0, the suite can't tell them apart yet, and you need more tests or more runs.

Pairing by test is what makes this work. A hard test drags both versions down equally, so its difficulty cancels out in the difference, and step counts don't need any extra normalising across tests. The list of per-test differences also shows exactly which tests regressed.

Tests compare against each other only through this pairing. A score of 0.9 on one test and 0.7 on another says little on its own, because the tests differ in difficulty.

### Alternative: a free step budget

Instead of dividing by goals listed, each task could get a budget B of steps that cost nothing, and only steps beyond it are discounted:

```
score = (goals met / goals listed) × d ^ max(0, steps − B)
```

B could be set from the gold actions (for example, the number of gold tool calls plus a small allowance). This is more precise but needs a B chosen per task, so the proposal starts with the simpler steps-per-goal version.

## Worked example

These are the five airline smoke tasks from the framework 1.6.6 run with structured output on, from [`../role-switch/framework-1.6.6-structured-smoke/summary_metrics.csv`](../role-switch/framework-1.6.6-structured-smoke/summary_metrics.csv). That run used the old v1 simulated user, so treat it as an illustration of the arithmetic, not as a result.

Goals here are the expected tool calls plus the one text goal, and steps follow [What counts as a step](#what-counts-as-a-step). The end-state goal is left out because the ADK can't measure it yet (see the next section), and none of these tasks has a forbidden action written down.

| Task | Goals met / listed | Steps (tool calls − `think`) | Completion | Efficiency | Score | `is_success` |
|---|---|---|---|---|---|---|
| 001 | 2 / 2 | 7 − 2 = 5 | 1.00 | 0.98^2.5 = 0.95 | **0.95** | True |
| 013 | 0 / 2 | 3 − 1 = 2 | 0.00 | 0.98^1 = 0.98 | **0.00** | False |
| 016 | 1 / 3 | 15 − 4 = 11 | 0.33 | 0.98^3.67 = 0.93 | **0.31** | False |
| 043 | 3 / 3 | 3 − 0 = 3 | 1.00 | 0.98^1 = 0.98 | **0.98** | True |
| 044 | 3 / 3 | 4 − 2 = 2 | 1.00 | 0.98^0.67 = 0.99 | **0.99** | True |
| Mean | | | | | **0.65** | 0.60 |

What the score adds over `is_success`: task 016 gets credit for the one call it got right instead of a flat 0, and task 001 is marked down for taking 5 steps where 1 was expected, which `is_success` treats the same as task 043's clean 3 for 3.

A comparison of two versions on these five tasks would then look like this (B's numbers are made up for illustration):

| Task | A (mean of n runs) | B (mean of n runs) | B − A |
|---|---|---|---|
| 001 | 0.95 | 0.98 | +0.03 |
| 013 | 0.00 | 0.65 | +0.65 |
| 016 | 0.31 | 0.31 | 0.00 |
| 043 | 0.98 | 0.94 | −0.04 |
| 044 | 0.99 | 0.99 | 0.00 |

Mean difference +0.13, with 2 wins, 2 ties and 1 loss. With only five tests the bootstrap interval is wide and almost certainly includes 0 (here most of the gain comes from one test), so the honest reading is "B looks better on 013, run the full suite before deciding".

## Mapping onto what we have

### Orchestrate eval output

Each results folder has a `summary_metrics.csv` with one row per test and run, plus `messages/<task>.messages.json`.

| Proposal | Orchestrate field |
|---|---|
| Required tool calls: goals listed | `expected_tool_calls` |
| Required tool calls: goals met | `correct_tool_calls` |
| Required info communicated | the `summarize` text goal: `text_match` (1 or 0), see also `text_match_comment` ("Matched 1/1 text goals") |
| Steps | tool calls in `messages.json` minus `think` calls. `total_tool_calls` includes `think`, and `total_steps` counts every message and LLM step |
| Forbidden action | not scored by the ADK. Can be checked from `messages.json` by looking for a forbidden tool call, or any write call that isn't a gold action |
| Correct end state | not available. Orchestrate runs each tool call in a fresh process, so there is no end-of-run database (see the main README). It could be rebuilt offline by replaying the run's write calls from `messages.json` through `airline/tools/airline_logic.py` or `retail/tools/retail_logic.py` and comparing the result with the gold actions replayed the same way |
| Runs per test | `run_idx` |

So the goal counts can be computed today from `summary_metrics.csv`, and the step count from `messages.json`. The end-state and forbidden-action goals can be added with a small script over `messages.json` too.

### tau2 `reward_basis`

tau2 scores a task as the product of the checks named in its `reward_basis`, each 0 or 1. Its components map onto the goal kinds:

| tau2 `reward_basis` | Goal kind |
|---|---|
| `DB` | correct end state |
| `ACTION` | required tool calls, one goal per gold action |
| `COMMUNICATE` | required info communicated, one goal per `communicate_info` item |
| `NL_ASSERTION` | required info communicated, judged by an LLM |

Two differences: tau2 multiplies the checks, so any failure gives 0 (our completion factor averages them instead, which is where partial credit comes from), and tau2 has no step penalty. A run that passes in tau2 is a run with completion 1.0 here, which is why pass^k uses the same definition of a pass.

All 114 retail tasks in `retail/source/tasks.json` use `DB` (112 also have `NL_ASSERTION`). Our port scores the gold actions as tool-call goals and `communicate_info` (present in 36 tasks) as keywords, since the ADK can't check the database.

## Open questions

- Whether the end-state goal should be rebuilt by replay now, or left out until it's needed.
- Where forbidden actions are written down. tau-bench tasks don't list them, so they would be a new field on each test case, written by hand for the tasks where the policy forbids something (for example, modifying a basic economy flight, which the airline policy doesn't allow).
- Whether d = 0.98 is the right strength once we have real multi-run numbers.
