"""Probe tools: does Orchestrate keep a Python tool's context updates for the rest of a conversation?

Each tool takes an ``AgentRun`` parameter. Orchestrate fills it at call time
with the run's context variables and hides it from the LLM. A tool writes
back by setting ``context.request_context[key]``; the ADK returns those keys as
``context_updates`` with the tool result.

If the updates persist across turns, the tau2 tools can carry their database
changes in the conversation context instead of in an external service.

Import with:

    orchestrate tools import -k python -f context_probe/tools/probe_tools.py \
        -r context_probe/tools/requirements.txt -p context_probe/tools
"""

import json

from ibm_watsonx_orchestrate.agent_builder.tools import ToolPermission, tool
from ibm_watsonx_orchestrate.run import AgentRun

NOTES_KEY = "probe_notes"


def _snapshot(context: AgentRun) -> dict:
    """Everything the tool received in its context, values shortened for display."""
    ctx = context.request_context if context is not None else {}
    return {k: (v if len(json.dumps(v, default=str)) <= 300 else f"<{type(v).__name__}, truncated>") for k, v in dict(ctx).items()}


@tool(permission=ToolPermission.READ_WRITE)
def probe_remember_note(note: str, context: AgentRun) -> str:
    """Store a note in the conversation context so later turns can read it back.

    Args:
        note: The note to store, such as 'alpha'.

    Returns:
        The stored notes and the context this call received, as JSON.
    """
    received = _snapshot(context)
    notes = list(context.request_context.get(NOTES_KEY) or [])
    notes.append(note)
    context.request_context[NOTES_KEY] = notes
    return json.dumps({"stored_notes": notes, "persisted_count_before_this_call": len(notes) - 1, "received_context": received})


@tool(permission=ToolPermission.READ_ONLY)
def probe_recall_notes(context: AgentRun) -> str:
    """Read back the notes stored by earlier probe_remember_note calls in this conversation.

    Returns:
        A line PERSISTED_COUNT=<n> NOTES=<comma-separated notes>, then the full context this call received as JSON.
    """
    notes = list(context.request_context.get(NOTES_KEY) or [])
    return f"PERSISTED_COUNT={len(notes)} NOTES={','.join(notes)}\n" + json.dumps({"received_context": _snapshot(context)})


@tool(permission=ToolPermission.READ_ONLY)
def probe_show_context(context: AgentRun) -> str:
    """Show every context variable this tool call received, such as the thread id or test-case runtime context.

    Returns:
        The context variables as JSON.
    """
    return json.dumps(_snapshot(context), default=str)
