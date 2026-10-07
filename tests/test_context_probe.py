"""Offline checks for the context persistence probe. None of these need an Orchestrate server."""

import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROBE = ROOT / "context_probe"
TEST_CASES = sorted((PROBE / "evaluations/test_cases").glob("*.json"))

sys.path.insert(0, str(PROBE / "tools"))


@pytest.fixture(scope="module")
def probe_tools():
    from ibm_watsonx_orchestrate.agent_builder.tools import PythonTool

    module = importlib.import_module("probe_tools")
    return {t.__tool_spec__.name: t for t in vars(module).values() if isinstance(t, PythonTool)}


def test_agent_spec_loads(probe_tools):
    from ibm_watsonx_orchestrate.agent_builder.agents import Agent

    agent = Agent.from_spec(str(PROBE / "agents/context_probe_agent.yaml"))
    assert agent.name == "context_probe_agent"
    assert sorted(agent.tools) == sorted(probe_tools)


def test_tools_bind_the_run_context(probe_tools):
    for name, t in probe_tools.items():
        assert t.__tool_spec__.binding.python.agent_run_paramater == "context", name


@pytest.mark.parametrize("path", TEST_CASES, ids=lambda p: p.stem)
def test_test_case_is_valid_adk(path, probe_tools):
    from agentops.type import TestCase

    case = TestCase.from_path(str(path))
    assert case.agent == "context_probe_agent"
    for goal in case.goal_details:
        if goal.type == "tool_call":
            assert goal.tool_name in probe_tools


def test_notes_persist_when_context_updates_are_carried(probe_tools):
    """What the probe should show if Orchestrate merges context_updates into later calls."""
    context = {}
    for note in ("alpha", "beta"):
        resp = probe_tools["probe_remember_note"](note=note, context={"request_context": dict(context)})
        context.update(resp.context_updates)
    recall = probe_tools["probe_recall_notes"](context={"request_context": context}).content
    assert recall.splitlines()[0] == "PERSISTED_COUNT=2 NOTES=alpha,beta"


def test_show_context_reports_runtime_context(probe_tools):
    shown = probe_tools["probe_show_context"](context={"request_context": {"probe_session": "case-42"}}).content
    assert json.loads(shown) == {"probe_session": "case-42"}
