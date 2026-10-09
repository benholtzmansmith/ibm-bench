# Proposal: improving the agents with eval design and hillclimbing

Status: proposal. Nothing here is built yet. It builds on the metric in [`../metrics/README.md`](../metrics/README.md) (draft PR #7) and does not redefine it: the per-run score, the step count, pass^k and the paired bootstrap comparison all come from there.

This adapts the method in [Automating eval design and hillclimbing](https://claude.dev/blog/automating-eval-design-and-hillclimbing/) to the airline and retail agents in this repo. The post's `/claude-api build-eval` and `/claude-api hillclimb` commands assume an app that calls the Claude API and an eval they build and run themselves. Our agents run inside watsonx Orchestrate and are scored by the ADK, so this proposal keeps the post's procedure and safeguards but plugs in our own runner, scorer and edit surfaces.

The work has two phases, in this order:

1. **Make the eval trustworthy** (the post's eval design principles). A hillclimber optimizes whatever the eval rewards, bugs included, so the eval gets checked first.
2. **Hillclimb** on a train split, gated by a held-out split the hillclimber never sees.

## Phase 1: make the eval trustworthy

The post's four tests of a good eval, and where each one stands here:

| Principle | Status in this repo | What to do |
|---|---|---|
| Tasks mirror production | The tasks are tau-bench and tau2, not IBM traffic. That's the point of the repo, so the benchmark *is* the target distribution for now. | Keep as is. If an IBM customer use case is added later, seed its eval from real transcripts and tickets first, as the post recommends, not from synthetic cases alone. |
| Score scales with capability | Unmeasured. | Run the full suite once with the agent on `watsonx-orchestrate/frontier` and once on a smaller model the instance lists. The stronger model should score higher. If it doesn't, suspect the simulated user or the judge before the agent. |
| Headroom | Not saturated: the airline smoke suite passes 3 or 4 of 5 (see [`../role-switch/`](../role-switch/)). | A task that fails every replicate on both models gets audited by hand before it counts (broken task or grader, or a real gap like task 013). |
| Low run-to-run variance | Known to be high: airline task 016 passed only when the simulated user kept pushing. | Measure it with the A/A run below and size n from it. |

### Checks to run before the first hillclimb round

Each one is a short script over a results folder (`summary_metrics.csv` and `messages/`), run on the baseline:

- **A/A noise floor.** Run the unchanged baseline twice, with n runs per test each time, and compare the two with the paired bootstrap from the metric proposal. The width of that interval is the smallest change the suite can detect. If it is wider than the smallest improvement worth keeping (say 0.03 on the mean score), raise n before hillclimbing. This is the post's "check that eval noise is smaller than the smallest improvement you would act on".
- **Plumbing.** Count runs with gateway errors, timeouts, runs that hit `max_user_turns: 30`, and simulated-user turns that break role (the v1 problem from [`../role-switch/`](../role-switch/); v2 fixed it, but a cheap detector keeps it fixed). These are infrastructure noise and are excluded or rerun, never scored as agent failures.
- **Judge consistency.** The `summarize` text goal is judged by an LLM. Re-judge a sample of saved transcripts twice and count verdicts that flip. If the ADK can't re-judge a saved transcript, compare `text_match` across repeat runs whose final responses are near identical. The judge model should not be the agent's model; today both are `watsonx-orchestrate/frontier`, so use a different instance model for the judge where one is available.
- **Read transcripts.** Before trusting the baseline, read about ten scored transcripts, including some passes, and confirm each verdict is the one a person would give. The post treats this as non-negotiable.

### Known eval gaps that a hillclimber would exploit

These come from how the ADK scores, and should be fixed or at least written down before hillclimbing:

- **No end state.** Orchestrate runs every tool call in a fresh process, so there is no final database, and the ADK scores tool calls instead. The replay idea in the metric proposal's open questions (replay the run's write calls through `*_logic.py` and compare with the gold actions replayed the same way) closes this. Recommended before hillclimbing, because without it an agent that makes the right calls with a wrong extra write still scores well.
- **No forbidden actions.** Nothing penalizes an unrequested write. At minimum, flag any write call that isn't a gold action, as the metric proposal suggests.
- **Keywords on the final response only.** tau2 checks `communicate_info` against every agent message; the ADK checks the last one. A hillclimber can learn to restate everything in a closing summary. Worth knowing; probably acceptable.
- **Fuzzy `transfer_to_human_agents.summary`.** Fine as is, but a change that games the summary wording is a red flag.

Fixes to the eval go in their own PRs, never inside a hillclimb round, so a score change can always be traced to either the agent or the eval.

## Phase 2: hillclimb

### What the hillclimber may change

The post's advice is to pick surfaces that are cheap to change, attributable and well scoped. For an Orchestrate native agent, in order of preference:

| Surface | Where | Allowed |
|---|---|---|
| Operating guidance | a new, clearly delimited section appended to `instructions` in `airline/agents/tau_airline_agent.yaml` and `retail/agents/tau2_retail_agent.yaml` | Yes. This is the main surface. |
| Tool descriptions | the docstrings in `airline/tools/airline_tools.py` and `retail/tools/retail_tools.py` | Yes, wording only. Names, arguments and return values stay as they are. |
| Agent `style` | `default`, `react` or `planner` in the agent YAML | Yes, one round per setting. |
| Agent model (`llm`) | the agent YAML, or the model picked in the instance UI | Yes, limited to models the instance lists. Mostly useful for a cost goal. |
| The benchmark policy text | the existing body of `instructions` | No. It defines what correct behavior is, and editing it changes the benchmark. Guidance may add to it but not delete or contradict it. |
| Tool logic and data | `*_logic.py`, `tools/data/` | No. That is the environment. |
| Test cases, eval configs, simulated user, judge | `evaluations/`, `source/`, `scripts/convert_*` | No. That is the eval. |

### Train and test splits

- **Retail:** use tau2's own split from `retail/source/split_tasks.json`: 74 train, 40 test. Using the upstream split keeps our numbers comparable with tau2 results.
- **Airline:** tau-bench ships only 50 test tasks. Split them 30 train and 20 test with a fixed seed, committed as `airline/evaluations/splits.json`, stratified so tasks that expect a transfer, a write, or no write appear on both sides.

Each benchmark gets `config.train.yaml` and `config.test.yaml`, generated from the split file.

### Each round

Following the post, one change per round:

1. **Analyze.** The analyzer (a Claude Code session) reads only the previous round's **train** transcripts and scores. It sorts failures by cause and proposes one patch that fixes a root cause: a missing rule, a misleading tool description. Rewording a line that already says the right thing doesn't count.
2. **Lint the patch** (see the safeguards below). A patch that fails is rejected without running.
3. **Import and run.** Import the patched agent and tools with `scripts/import_<benchmark>.sh`, then run the train and test configs with n runs per test.
4. **Score and compare** against the current best version with the metric proposal's paired bootstrap, separately on train and test.
5. **Keep or revert.** Keep the patch only if the train mean improves beyond the A/A noise floor, the test mean difference is above 0, and test pass^1 does not drop. Revert if only train improves (the post's overfitting signal), or if either side regresses.
6. **Log** the patch, both comparisons and the decision to `hillclimb/<benchmark>/<date>/log.jsonl`, and commit the kept version on the hillclimb branch.

**When it stalls** (two or three rounds with nothing kept), stop patching and read every remaining train failure. Sort each into: agent failure, ambiguous task, grader error, ADK artifact (for example, a later read not seeing an earlier write because state doesn't persist), or noise. Only agent failures go into further rounds. The rest become eval issues for their own PRs, which is how the post's claude-api run found a grader that contradicted the docs.

**At the end,** leave the agent at the best test-set version and report it against the original baseline on the test split, with the paired bootstrap interval, win/tie/loss, pass^1 and pass^3. If the interval includes 0, say so and don't merge.

### Safeguards against overfitting and leakage

tau-bench and tau2 are public, gold actions included, which makes leakage the main risk here.

- **The analyzer never sees test transcripts or test scores**, only the keep/revert decision. It runs with read access to the train results folder and the editable files, not to `*/source/`, `*/evaluations/test_cases/` or the test results.
- **No task specifics in a patch.** A lint rejects any patch whose diff contains a user ID, reservation ID, order ID, product or item ID, flight number or person's name from `tools/data/`, or any phrase longer than a few words copied from a test case story. This turns the post's "never paste failures into the prompt" into a check.
- **Policy text intact.** The lint also checks that the original policy is still a verbatim substring of `instructions`, and that only the allowed files changed.
- **Test reuse.** The test split gates every round, so by the end it has been used for selection and its number is slightly optimistic. Keep the number of rounds small (cap at about ten) and, before merging, rerun the final version against the baseline on the test split with fresh runs and a larger n.

### Objectives

Start with performance: the mean efficiency-adjusted score from the metric proposal, with pass^k reported next to it. The score already discounts extra steps, so efficiency is part of the target.

Once performance stops moving, switch to the post's other default goal, cost at parity: try the instance's cheaper models and lighter guidance, and keep a change only if the test score is not worse beyond the noise floor. Cost per conversation comes from token counts if the ADK reports them, otherwise from LLM steps.

### Cost of a round

With n = 3, an airline round is (30 + 20) × 3 = 150 simulated conversations and a retail round is (74 + 40) × 3 = 342, each with an agent, a simulated user and a judge calling the model. On the trial instance that may hit quota limits, so check the instance's limits before starting, run airline first, and use `num_workers` to stay within rate limits.

## What to build

| Piece | Path | Notes |
|---|---|---|
| Scorer | `scripts/score.py` | The metric proposal's per-run score, steps, pass^k from a results folder. Prerequisite for everything else. |
| Paired comparison | `scripts/compare.py` | Two results folders in, mean difference, bootstrap interval and win/tie/loss out. |
| End-state replay | `scripts/replay_end_state.py` | Optional but recommended (see the known gaps above). |
| Splits | `airline/evaluations/splits.json`, `config.{train,test}.yaml` for both benchmarks | Generated by a small script with a fixed seed. |
| Health checks | `scripts/eval_health.py` | A/A width, plumbing counts, role-break detector, judge flip rate. |
| Patch lint | `scripts/check_patch.py` | Allowed files, policy substring intact, no data identifiers or story text. Also runs in `pytest`. |
| Loop driver | `scripts/hillclimb.sh` | Import, run train and test, score, compare, keep or revert, log. The analyzer step is a Claude Code session working on a branch. |

Whether `/claude-api hillclimb` can drive this directly with `scripts/hillclimb.sh` as its runner is untested. If it can, it replaces the loop driver and keeps the same splits, keep rule and lint. If not, the loop above is small enough to run by hand or from a Claude Code session.

## Suggested order

1. Merge the metric proposal (PR #7) and build `score.py` and `compare.py`.
2. Add the splits and train and test configs.
3. Run the baseline twice (A/A) on airline with n = 3, run the health checks, and read transcripts. Fix eval issues in separate PRs.
4. Run the capability check (two models).
5. Hillclimb airline on performance. Task 013 (agent refuses instead of transferring) is a known real failure; if 013 lands in train, it's a natural first target, fixed as a general rule about when to transfer and never as a rule about that reservation.
6. Repeat for retail.
7. Switch the goal to cost at parity.

## Open questions

- Whether the operating guidance lives in `instructions` or in the ADK agent's `guidelines` field, if the instance's ADK version supports it. `guidelines` would keep the policy and the guidance physically separate, which makes the lint simpler.
- Which ADK config key sets n runs per test (the `run_idx` column suggests repeats are supported).
- Whether the instance has a second model good enough to act as an independent judge.
- Whether to build end-state replay before the first round or after the first stall.
