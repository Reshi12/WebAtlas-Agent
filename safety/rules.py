"""Hard safety rules enforcement — backend-agnostic.

These rules are NEVER bypassed regardless of which backend (agent-browser or
Webwright) produced the action. They are called from ``safety_gate_node`` which
sits outside both backends in the LangGraph state machine.

Rules (ordered by severity):
  1. Payment pages → hard stop, zero exceptions.
  2. Login pages → pause, ask user to log in manually.
  3. Personal-info fields → agent fills safe fields, pauses for the rest.
  4. Destructive actions → always require explicit confirmation.
"""

from __future__ import annotations

import logging
from typing import Any

from core.state import AgentState, PageClassification

logger = logging.getLogger(__name__)


def enforce_safety_gate(
    state: AgentState,
    page_classification: PageClassification,
) -> AgentState:
    """Apply hard safety rules based on page classification.

    Returns a partial state update. If the page is safe, returns minimal
    changes. If unsafe, sets ``status`` to ``awaiting_human`` with the
    appropriate ``interrupt_reason`` and ``interrupt_message``.
    """
    updates: dict[str, Any] = {"page_classification": page_classification}

    # ── Rule 1: Payment page — HARD STOP ─────────────────────────────────
    if page_classification.get("is_payment_page", False):
        logger.warning("SAFETY: Payment page detected — hard stop.")
        updates.update(
            status="awaiting_payment_resume",
            interrupt_reason="payment",
            interrupt_message=(
                "⚠️  Payment page detected. I will NOT interact with this page.\n"
                "    Please complete payment yourself in the browser window,\n"
                "    then type 'resume' to continue."
            ),
        )
        return updates  # type: ignore[return-value]

    # ── Rule 2: Login page — pause for manual login ──────────────────────
    if page_classification.get("is_login_page", False):
        logger.warning("SAFETY: Login page detected — pausing for manual login.")
        updates.update(
            status="awaiting_human",
            interrupt_reason="login",
            interrupt_message=(
                "🔒 Login page detected. Please log in manually in the browser\n"
                "   window, then type 'done' to continue."
            ),
        )
        return updates  # type: ignore[return-value]

    # ── Rule 3: Personal-info fields — partial handoff ───────────────────
    human_fields = page_classification.get("human_required_fields", [])
    agent_fields = page_classification.get("agent_fillable_fields", [])
    if human_fields:
        filled_str = ", ".join(agent_fields) if agent_fields else "(none)"
        needed_str = ", ".join(human_fields)
        logger.info(
            "SAFETY: Personal-info fields detected — agent filled [%s], "
            "needs human for [%s]",
            filled_str,
            needed_str,
        )
        updates.update(
            status="awaiting_human",
            interrupt_reason="personal_info",
            interrupt_message=(
                f"📝 I've filled in: {filled_str}\n"
                f"   Please fill in: {needed_str}\n"
                f"   Type 'done' when ready and I'll review before submitting."
            ),
        )
        return updates  # type: ignore[return-value]

    # ── Page is safe — no interrupt ──────────────────────────────────────
    return updates  # type: ignore[return-value]


def requires_destructive_confirmation(action_description: str, keywords: set[str]) -> str | None:
    """Check if an action needs explicit user confirmation before executing.

    Returns a confirmation prompt string if the action is destructive,
    or None if it's safe to proceed.
    """
    action_lower = action_description.lower()
    matched = [kw for kw in keywords if kw in action_lower]
    if matched:
        return (
            f"⚠️  This action appears destructive (matched: {', '.join(matched)}).\n"
            f"   Action: {action_description}\n"
            f"   Proceed? (yes/no)"
        )
    return None


def is_awaiting_human(state: AgentState) -> bool:
    """Guard clause: returns True if the agent should NOT act.

    Both ``agent_browser_actor`` and ``webwright_actor`` call this before
    doing anything — defense in depth on top of the graph-level routing.
    """
    return state.get("status", "running") in (
        "awaiting_human",
        "awaiting_payment_resume",
    )
