#!/usr/bin/env python3
"""Convert tau2-bench retail tasks into watsonx Orchestrate ADK evaluation test cases.

Input:  retail/source/tasks.json and split_tasks.json, copied from
        tau2-bench data/tau2/domains/retail. The default split is tau2's
        `base` split, all 114 tasks, which is what tau2 evaluates by default.
Output: retail/evaluations/test_cases/retail_task_NNN.json, one ADK test case
        per task, numbered by tau2 task id.

Mapping:
  user_scenario                     -> story, rendered as tau2 renders it for its user simulator
  evaluation_criteria.actions       -> tool_call goals, ordered so that each write waits for the
                                       actions before it, while reads before a write may run in any order
  evaluation_criteria.compare_args  -> arguments outside the list are ignored
  evaluation_criteria.communicate_info -> keywords the final agent response must contain
  evaluation_criteria.nl_assertions -> appended to the expected final response
"""

import argparse
import json
import sys
import textwrap
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENT_NAME = "tau2_retail_agent"

sys.path.insert(0, str(ROOT / "retail/tools"))
from retail_logic import READ_ONLY  # noqa: E402

# Arguments a correct agent may phrase differently from the gold action.
ARG_MATCHING = {
    "calculate": {"expression": "ignore"},
    "transfer_to_human_agents": {"summary": "fuzzy"},
}


def render_story(scenario: dict) -> str:
    """Same text as str(tau2.data_model.tasks.UserScenario)."""
    tab = "\t"
    ins = scenario["instructions"]
    if isinstance(ins, str):
        instructions = ins
    else:
        lines = [f"Domain: {ins['domain']}", f"Reason for call:\n{textwrap.indent(ins['reason_for_call'], tab)}"]
        if ins.get("known_info") is not None:
            lines.append(f"Known info:\n{textwrap.indent(ins['known_info'], tab)}")
        if ins.get("unknown_info") is not None:
            lines.append(f"Unknown info:\n{textwrap.indent(ins['unknown_info'], tab)}")
        lines.append(f"Task instructions:\n{textwrap.indent(ins['task_instructions'], tab)}")
        instructions = "\n".join(lines)
    lines = []
    if scenario.get("persona") is not None:
        lines += ["Persona:", textwrap.indent(scenario["persona"], tab)]
    lines += ["Instructions:", textwrap.indent(instructions, tab)]
    return "\n".join(lines)


def describe(name: str, kwargs: dict) -> str:
    if name == "cancel_pending_order":
        return f"cancelled order {kwargs['order_id']} because it was {kwargs['reason']}"
    if name == "exchange_delivered_order_items":
        return (
            f"exchanged items {', '.join(kwargs['item_ids'])} in order {kwargs['order_id']} "
            f"for {', '.join(kwargs['new_item_ids'])}, settling the difference with {kwargs['payment_method_id']}"
        )
    if name == "modify_pending_order_items":
        return (
            f"changed items {', '.join(kwargs['item_ids'])} in order {kwargs['order_id']} "
            f"to {', '.join(kwargs['new_item_ids'])}, settling the difference with {kwargs['payment_method_id']}"
        )
    if name == "return_delivered_order_items":
        return (
            f"returned items {', '.join(kwargs['item_ids'])} from order {kwargs['order_id']} "
            f"with the refund to {kwargs['payment_method_id']}"
        )
    if name == "modify_pending_order_address":
        return f"changed the shipping address of order {kwargs['order_id']} to {_address(kwargs)}"
    if name == "modify_pending_order_payment":
        return f"changed the payment method of order {kwargs['order_id']} to {kwargs['payment_method_id']}"
    if name == "modify_user_address":
        return f"changed the default address of {kwargs['user_id']} to {_address(kwargs)}"
    if name == "transfer_to_human_agents":
        return "transferred the user to a human agent"
    raise ValueError(f"no description for write action {name}")


def _address(kwargs: dict) -> str:
    parts = [kwargs["address1"], kwargs["address2"], kwargs["city"], kwargs["state"], kwargs["zip"], kwargs["country"]]
    return ", ".join(p for p in parts if p)


def convert(task: dict) -> dict:
    criteria = task["evaluation_criteria"]
    actions = criteria["actions"]
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
            "args": action["arguments"],
        }
        matching = dict(ARG_MATCHING.get(action["name"], {}))
        if action.get("compare_args") is not None:
            for arg in action["arguments"]:
                if arg not in action["compare_args"]:
                    matching[arg] = "ignore"
        if matching:
            detail["arg_matching"] = matching
        goal_details.append(detail)

    # Each action points at the next write (or the final summary), so writes stay
    # in tau2's order and the reads leading up to a write are unordered.
    goals = {}
    for i, (goal_name, action) in enumerate(zip(goal_names, actions)):
        nxt = next(
            (goal_names[j] for j in range(i + 1, len(actions)) if actions[j]["name"] not in READ_ONLY),
            "summarize",
        )
        goals[goal_name] = [nxt]
    if not actions:
        goals["summarize"] = []

    writes = [describe(a["name"], a["arguments"]) for a in actions if a["name"] not in READ_ONLY]
    if writes:
        response = "The agent " + "; ".join(writes) + "."
    else:
        response = "The agent did not change any order or user."
    communicate = criteria.get("communicate_info") or []
    if communicate:
        response += " The agent told the user: " + ", ".join(communicate) + "."
    for assertion in criteria.get("nl_assertions") or []:
        response += " " + assertion
    summarize = {"type": "text", "name": "summarize", "response": response, "keywords": communicate}
    goal_details.append(summarize)

    return {
        "agent": AGENT_NAME,
        "story": render_story(task["user_scenario"]),
        "goals": goals,
        "goal_details": goal_details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tasks", type=Path, default=ROOT / "retail/source/tasks.json")
    parser.add_argument("--splits", type=Path, default=ROOT / "retail/source/split_tasks.json")
    parser.add_argument("--split", default="base", help="tau2 task split: base (default), train or test")
    parser.add_argument("--out", type=Path, default=ROOT / "retail/evaluations/test_cases")
    args = parser.parse_args()

    tasks = json.loads(args.tasks.read_text())
    wanted = set(json.loads(args.splits.read_text())[args.split])
    tasks = [t for t in tasks if t["id"] in wanted]
    args.out.mkdir(parents=True, exist_ok=True)
    for task in tasks:
        path = args.out / f"retail_task_{int(task['id']):03d}.json"
        path.write_text(json.dumps(convert(task), indent=2) + "\n")
    print(f"wrote {len(tasks)} test cases to {args.out}")


if __name__ == "__main__":
    main()
