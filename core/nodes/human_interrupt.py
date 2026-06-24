"""Human interrupt node — pause/resume logic for safety handoffs.

Uses LangGraph's native ``interrupt()`` mechanism to pause the graph
execution and return control to the CLI. When the user types ``resume``,
``done``, or ``yes``, the graph resumes exactly where it left off.

This works identically whether the pause happened mid-agent-browser-sequence
or mid-Webwright-script — LangGraph's SQLite checkpointer serializes and
restores the full state transparently.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.types import interrupt

from core.state import AgentState

logger = logging.getLogger(__name__)


def make_human_interrupt_node(config: dict[str, Any]):
    """Factory: creates the human interrupt node."""

    def human_interrupt_node(state: AgentState) -> dict[str, Any]:
        """Pause the graph and wait for human input.
