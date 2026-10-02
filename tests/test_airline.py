"""Offline checks for the airline port. None of these need an Orchestrate server."""

import copy
import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
AIRLINE = ROOT / "airline"
TOOLS_DIR = AIRLINE / "tools"
TEST_CASES = sorted((AIRLINE / "evaluations/test_cases").glob("*.json"))
TAU_TASKS = json.loads((AIRLINE / "source/tasks_test.json").read_text())

sys.path.insert(0, str(TOOLS_DIR))
airline_logic = importlib.import_module("airline_logic")
BASE_DATA = airline_logic.load_data()


@pytest.fixture(scope="module")
def adk_tools():
    from ibm_watsonx_orchestrate.agent_builder.tools import PythonTool

    module = importlib.import_module("airline_tools")
    return {t.__tool_spec__.name: t for t in vars(module).values() if isinstance(t, PythonTool)}


@pytest.fixture(scope="module")
def agent_spec():
    return yaml.safe_load((AIRLINE / "agents/tau_airline_agent.yaml").read_text())


def test_agent_spec_loads():
    from ibm_watsonx_orchestrate.agent_builder.agents import Agent

    agent = Agent.from_spec(str(AIRLINE / "agents/tau_airline_agent.yaml"))
    assert agent.name == "tau_airline_agent"
    assert agent.llm.startswith("virtual-model/")


def test_agent_instructions_are_tau_policy(agent_spec):
    wiki = (AIRLINE / "source/wiki.md").read_text()
    assert agent_spec["instructions"].strip() == wiki.strip()


def test_agent_uses_every_tool(adk_tools, agent_spec):
    assert sorted(agent_spec["tools"]) == sorted(adk_tools)
    assert sorted(adk_tools) == sorted(airline_logic.ACTIONS)


def test_model_spec_matches_agent_llm(agent_spec):
    model = yaml.safe_load((AIRLINE / "models/claude_sonnet.yaml").read_text())
    assert agent_spec["llm"] == f"virtual-model/{model['name']}"
    for suite in ("smoke", "full"):
        config = yaml.safe_load((AIRLINE / f"evaluations/config.{suite}.yaml").read_text())
        assert config["llm_user_config"]["provider_config"]["model_id"] == agent_spec["llm"]
        assert config["evaluation_config"]["provider_config"]["model_id"] == agent_spec["llm"]


def test_test_cases_are_up_to_date(tmp_path):
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/convert_tau_tasks.py"), "--out", str(tmp_path)],
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
    assert case.agent == "tau_airline_agent"
    for goal in case.goal_details:
        if goal.type != "tool_call":
            continue
        schema = adk_tools[goal.tool_name].__tool_spec__.input_schema
        assert set(goal.args) <= set(schema.properties), goal.name
        assert set(schema.required or []) <= set(goal.args), goal.name


@pytest.mark.parametrize("index", range(len(TAU_TASKS)))
def test_gold_actions_replay_cleanly(index):
    """Running tau-bench's gold actions in order through the port succeeds."""
    data = copy.deepcopy(BASE_DATA)
    for action in TAU_TASKS[index]["actions"]:
        result = airline_logic.ACTIONS[action["name"]](data, **action["kwargs"])
        assert not str(result).startswith("Error"), (action["name"], result)


def test_adk_wrapper_matches_logic(adk_tools):
    task = TAU_TASKS[0]["actions"][0]
    expected = airline_logic.book_reservation(airline_logic.load_data(), **task["kwargs"])
    actual = adk_tools["book_reservation"](**task["kwargs"]).content
    assert json.loads(actual) == json.loads(expected)
