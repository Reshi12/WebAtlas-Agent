"""AgentState schema for the browser agent LangGraph state machine.

This is the single source of truth for all state carried through the graph.
Every node reads from and writes partial updates back to this state.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph.message import add_messages


# ── Supporting types ─────────────────────────────────────────────────────────


class PlanStep(TypedDict):
    """A single step in the agent's execution plan."""

    step: str  # human-readable description of what to do
    backend: Literal["agent_browser", "webwright"]  # which backend executes this
    details: str  # additional context for the backend


class StepRecord(TypedDict, total=False):
    """Record of a single executed step, stored in step_history."""

    step: str
    backend: Literal["agent_browser", "webwright"]
    action: str  # the concrete action taken (e.g., "click @e12", "ran script")
    result: str  # what happened after the action
