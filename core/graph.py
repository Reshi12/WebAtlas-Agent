"""LangGraph state machine — the orchestration core of the browser agent.

Wires all nodes together with the routing logic described in the plan:

    START → planner → router → [agent_browser_actor | webwright_actor]
        → safety_gate → [verifier | human_interrupt]
        → [advance_step → router (loop) | retry → router | replan → router]
        → END

The safety gate sits outside both backends, so neither can bypass it.
LangGraph's interrupt mechanism + MemorySaver checkpointer handles pause/resume
transparently.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from core.browser_session import BrowserSession
from core.llm_provider import AgentLLM
from core.nodes.agent_browser_actor import make_agent_browser_actor_node
from core.nodes.human_interrupt import make_human_interrupt_node
from core.nodes.planner import make_planner_node, make_replan_node
from core.nodes.safety_gate import make_safety_gate_node
from core.nodes.verifier import make_verifier_node
from core.nodes.webwright_actor import make_webwright_actor_node
from core.state import AgentState

logger = logging.getLogger(__name__)


# ── Routing functions ────────────────────────────────────────────────────────


def route_to_backend(state: AgentState) -> str:
    """Route the current step to the appropriate backend, or end if done.

    This is a conditional edge function — returns the name of the next node.
    """
    plan = state.get("plan", [])
    idx = state.get("current_step_index", 0)
    status = state.get("status", "running")

    if status in ("done", "failed"):
        return "end_node"

    if idx >= len(plan):
        return "end_node"
