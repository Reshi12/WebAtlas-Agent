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
