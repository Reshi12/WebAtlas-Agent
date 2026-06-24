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

        The ``interrupt()`` call suspends execution. When the user provides
        input via ``graph.invoke(Command(resume=value), config)``, execution
        resumes here with the user's response.
        """
        reason = state.get("interrupt_reason", "unknown")
        message = state.get("interrupt_message", "Agent paused — please respond.")

        logger.info("[human_interrupt] Pausing — reason: %s", reason)

        # This suspends the graph and returns control to the CLI
        human_response = interrupt({
            "reason": reason,
            "message": message,
        })

        # ── Execution resumes here after user responds ───────────────────
        logger.info("[human_interrupt] Resumed with response: %s", human_response)

        response_lower = str(human_response).strip().lower()

        # Handle different resume scenarios
        if reason == "payment":
            # User completed payment manually
            logger.info("[human_interrupt] Payment completed by user — resuming")
            return {
                "status": "running",
                "interrupt_reason": None,
                "interrupt_message": None,
                "retry_count": 0,
            }

        elif reason == "login":
            # User logged in manually
            logger.info("[human_interrupt] Login completed by user — resuming")
            return {
                "status": "running",
                "interrupt_reason": None,
                "interrupt_message": None,
                "retry_count": 0,
            }

        elif reason == "personal_info":
            # User filled in personal fields
            logger.info("[human_interrupt] Personal info filled by user — resuming")
            return {
                "status": "running",
                "interrupt_reason": None,
                "interrupt_message": None,
                # Don't reset retry_count here — the next action
                # will be the submit confirmation
            }

        elif reason == "destructive":
            # User confirmed or denied a destructive action
            if response_lower in ("yes", "y", "proceed", "confirm"):
                logger.info("[human_interrupt] Destructive action confirmed")
                return {
                    "status": "running",
                    "interrupt_reason": None,
                    "interrupt_message": None,
                }
            else:
                logger.info("[human_interrupt] Destructive action denied — skipping step")
                return {
                    "status": "running",
                    "interrupt_reason": None,
                    "interrupt_message": None,
                    "error_message": "User declined destructive action",
                }

        else:
            # Generic resume
            logger.info("[human_interrupt] Generic resume")
            return {
                "status": "running",
                "interrupt_reason": None,
                "interrupt_message": None,
            }

    return human_interrupt_node
