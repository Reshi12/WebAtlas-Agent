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

