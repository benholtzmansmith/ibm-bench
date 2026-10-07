"""Offline checks for the tau2 retail port. None of these need an Orchestrate server."""

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
RETAIL = ROOT / "retail"
TOOLS_DIR = RETAIL / "tools"
TEST_CASES = sorted((RETAIL / "evaluations/test_cases").glob("*.json"))
TAU2_TASKS = json.loads((RETAIL / "source/tasks.json").read_text())

sys.path.insert(0, str(TOOLS_DIR))
retail_logic = importlib.import_module("retail_logic")
BASE_DATA = retail_logic.load_data()


@pytest.fixture(scope="module")
def adk_tools():
    from ibm_watsonx_orchestrate.agent_builder.tools import PythonTool

    module = importlib.import_module("retail_tools")
    return {t.__tool_spec__.name: t for t in vars(module).values() if isinstance(t, PythonTool)}


@pytest.fixture(scope="module")
def agent_spec():
    return yaml.safe_load((RETAIL / "agents/tau2_retail_agent.yaml").read_text())


def test_agent_spec_loads():
    from ibm_watsonx_orchestrate.agent_builder.agents import Agent

    agent = Agent.from_spec(str(RETAIL / "agents/tau2_retail_agent.yaml"))
    assert agent.name == "tau2_retail_agent"
    assert agent.llm.startswith("virtual-model/")


def test_agent_instructions_are_tau2_policy(agent_spec):
    policy = (RETAIL / "source/policy.md").read_text()
    assert agent_spec["instructions"].strip() == policy.strip()


def test_agent_uses_every_tool(adk_tools, agent_spec):
    assert sorted(agent_spec["tools"]) == sorted(adk_tools)
    assert sorted(adk_tools) == sorted(retail_logic.ACTIONS)


def test_model_spec_matches_agent_llm(agent_spec):
    model = yaml.safe_load((RETAIL / "models/claude_sonnet.yaml").read_text())
    assert agent_spec["llm"] == f"virtual-model/{model['name']}"
    for suite in ("smoke", "full"):
        config = yaml.safe_load((RETAIL / f"evaluations/config.{suite}.yaml").read_text())
        assert config["llm_user_config"]["provider_config"]["model_id"] == agent_spec["llm"]
        assert config["evaluation_config"]["provider_config"]["model_id"] == agent_spec["llm"]
        for path in config["test_paths"]:
            assert (ROOT / path).exists(), path


def test_test_cases_are_up_to_date(tmp_path):
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/convert_tau2_retail_tasks.py"), "--out", str(tmp_path)],
        check=True,
        capture_output=True,
    )
    generated = sorted(tmp_path.glob("*.json"))
    assert [p.name for p in generated] == [p.name for p in TEST_CASES]
    for fresh, committed in zip(generated, TEST_CASES):
        assert fresh.read_text() == committed.read_text(), committed.name


@pytest.mark.parametrize("path", TEST_CASES, ids=lambda p: p.stem)
def test_test_case_is_valid_adk(path, adk_tools):
    from agentops.type import TestCase

    case = TestCase.from_path(str(path))
    assert case.agent == "tau2_retail_agent"
    for goal in case.goal_details:
        if goal.type != "tool_call":
            continue
        schema = adk_tools[goal.tool_name].__tool_spec__.input_schema
        assert set(goal.args) <= set(schema.properties), goal.name
        assert set(schema.required or []) <= set(goal.args), goal.name


# Gold actions that return an error in tau2 itself: lookups of a wrong email,
# name or id that the user corrects later, and two writes the policy expects to fail.
TAU2_FAILING_GOLD_ACTIONS = {
    "2_1", "3_1", "4_1", "35_0", "37_0", "38_0", "39_0", "46_1", "46_2",
    "47_1", "47_2", "54_0", "55_0", "64_6", "67_0", "67_1", "68_0", "106_0",
}  # fmt: skip


@pytest.mark.parametrize("index", range(len(TAU2_TASKS)))
def test_gold_actions_replay_like_tau2(index):
    """Running tau2's gold actions in order through the port fails only where tau2 fails."""
    data = BASE_DATA.model_copy(deep=True)
    for action in TAU2_TASKS[index]["evaluation_criteria"]["actions"]:
        result = retail_logic.ACTIONS[action["name"]](data, **action["arguments"])
        expect_error = action["action_id"] in TAU2_FAILING_GOLD_ACTIONS
        assert result.startswith("Error") == expect_error, (action["action_id"], result)


@pytest.mark.parametrize("index", range(len(TAU2_TASKS)))
def test_gold_actions_succeed_without_carried_state(index):
    """Orchestrate starts every tool call from the pristine database; no gold action depends on an earlier write."""
    for action in TAU2_TASKS[index]["evaluation_criteria"]["actions"]:
        result = retail_logic.ACTIONS[action["name"]](BASE_DATA.model_copy(deep=True), **action["arguments"])
        expect_error = action["action_id"] in TAU2_FAILING_GOLD_ACTIONS
        assert result.startswith("Error") == expect_error, (action["action_id"], result)


def test_writes_change_state_like_tau2():
    data = BASE_DATA.model_copy(deep=True)
    order = json.loads(retail_logic.cancel_pending_order(data, order_id="#W5056519", reason="ordered by mistake"))
    assert order["status"] == "cancelled"
    assert data.orders["#W5056519"].status == "cancelled"
    again = retail_logic.cancel_pending_order(data, order_id="#W5056519", reason="ordered by mistake")
    assert again == "Error: Non-pending order cannot be cancelled"


def test_adk_wrapper_matches_logic(adk_tools):
    action = TAU2_TASKS[0]["evaluation_criteria"]["actions"][-1]
    assert action["name"] == "exchange_delivered_order_items"
    expected = retail_logic.exchange_delivered_order_items(retail_logic.load_data(), **action["arguments"])
    actual = adk_tools[action["name"]](**action["arguments"]).content
    assert json.loads(actual) == json.loads(expected)
