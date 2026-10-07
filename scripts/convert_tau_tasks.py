#!/usr/bin/env python3
"""Convert tau-bench airline tasks into watsonx Orchestrate ADK evaluation test cases.

Input:  airline/source/tasks_test.json, the 50 tasks from
        tau_bench/envs/airline/tasks_test.py exported to JSON.
Output: airline/evaluations/test_cases/airline_task_NNN.json, one ADK test case per task.

Mapping:
  instruction -> story (the LLM user simulator plays the user from it, as in tau-bench)
  actions     -> tool_call goals, ordered so that each write waits for the
                 actions before it, while reads before a write may run in any order
  outputs     -> keywords the final agent response must contain
"""

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENT_NAME = "tau_airline_agent"

READ_ONLY = {
    "calculate",
    "get_reservation_details",
    "get_user_details",
    "list_all_airports",
    "search_direct_flight",
    "search_onestop_flight",
    "think",
}

# Arguments a correct agent may phrase differently from the gold action.
ARG_MATCHING = {
    "calculate": {"expression": "ignore"},
    "think": {"thought": "ignore"},
    "transfer_to_human_agents": {"summary": "fuzzy"},
}


def describe(name: str, kwargs: dict) -> str:
    if name == "book_reservation":
        legs = ", ".join(f"{f['flight_number']} on {f['date']}" for f in kwargs["flights"])
        return (
            f"booked a {kwargs['flight_type'].replace('_', ' ')} {kwargs['cabin'].replace('_', ' ')} "
            f"reservation from {kwargs['origin']} to {kwargs['destination']} ({legs})"
        )
    if name == "cancel_reservation":
        return f"cancelled reservation {kwargs['reservation_id']}"
    if name == "update_reservation_flights":
        legs = ", ".join(f"{f['flight_number']} on {f['date']}" for f in kwargs["flights"])
        return (
            f"updated reservation {kwargs['reservation_id']} to {kwargs['cabin'].replace('_', ' ')} "
            f"with flights {legs}"
        )
    if name == "update_reservation_baggages":
        return (
            f"updated reservation {kwargs['reservation_id']} to {kwargs['total_baggages']} bags "
            f"({kwargs['nonfree_baggages']} paid)"
        )
    if name == "update_reservation_passengers":
        return f"updated the passengers on reservation {kwargs['reservation_id']}"
    if name == "send_certificate":
        return f"sent a ${kwargs['amount']} certificate to {kwargs['user_id']}"
    if name == "transfer_to_human_agents":
        return "transferred the user to a human agent"
    raise ValueError(f"no description for write action {name}")


def convert(task: dict) -> dict:
    actions = task["actions"]
    counts = Counter()
    goal_names = []
    goal_details = []
    for action in actions:
        counts[action["name"]] += 1
        goal_name = f"{action['name']}-{counts[action['name']]}"
        goal_names.append(goal_name)
        detail = {
            "type": "tool_call",
            "name": goal_name,
            "tool_name": action["name"],
            "args": action["kwargs"],
        }
        if action["name"] in ARG_MATCHING:
            detail["arg_matching"] = ARG_MATCHING[action["name"]]
        goal_details.append(detail)

    # Each action points at the next write (or the final summary), so writes stay
    # in tau-bench's order and the reads leading up to a write are unordered.
    goals = {}
    for i, (goal_name, action) in enumerate(zip(goal_names, actions)):
        nxt = next(
            (goal_names[j] for j in range(i + 1, len(actions)) if actions[j]["name"] not in READ_ONLY),
            "summarize",
        )
        goals[goal_name] = [nxt]
    if not actions:
        goals["summarize"] = []

    writes = [describe(a["name"], a["kwargs"]) for a in actions if a["name"] not in READ_ONLY]
    if writes:
        response = "The agent " + "; ".join(writes) + "."
    else:
        response = "The agent did not change any reservation, because the request is not allowed under the airline policy."
    if task["outputs"]:
        response += " The agent told the user: " + ", ".join(task["outputs"]) + "."
    summarize = {"type": "text", "name": "summarize", "response": response, "keywords": task["outputs"]}
    goal_details.append(summarize)

    return {
        "agent": AGENT_NAME,
        "story": task["instruction"],
        "goals": goals,
        "goal_details": goal_details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tasks", type=Path, default=ROOT / "airline/source/tasks_test.json")
    parser.add_argument("--out", type=Path, default=ROOT / "airline/evaluations/test_cases")
    args = parser.parse_args()

    tasks = json.loads(args.tasks.read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    for index, task in enumerate(tasks):
        path = args.out / f"airline_task_{index:03d}.json"
        path.write_text(json.dumps(convert(task), indent=2) + "\n")
    print(f"wrote {len(tasks)} test cases to {args.out}")


if __name__ == "__main__":
    main()
