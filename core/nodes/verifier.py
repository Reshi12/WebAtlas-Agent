"""Verifier node — checks whether a step actually succeeded.

Uses the cheap model first (it's a simple yes/no classification on the
post-action page state). Falls back to the strong model only if the cheap
model's answer is uncertain.

Also handles the retry → replan escalation logic:
  - retry_count < max_retries → retry the same step
  - retry_count >= max_retries → escalate to replan_node
"""

from __future__ import annotations

import json
import logging
from typing import Any

from core.llm_provider import AgentLLM
from core.state import AgentState

logger = logging.getLogger(__name__)

VERIFY_SYSTEM_PROMPT = """\
You are a verification agent. Given the step that was just executed, the
action taken, the result, and the current page state, determine whether
the step was successful.

## Rules
- A step is successful if its intended outcome is reflected in the page
  state or action result.
- Be lenient with partial success (e.g. "item added to cart" even if the
  exact confirmation text differs slightly).
- If the page changed in a way that indicates progress toward the goal,
  that counts as success.
- If the page shows an error, timeout, or is unchanged from before the
  action, that's a failure.

## Output Format (JSON)
{
  "success": true/false,
  "confidence": "high"|"medium"|"low",
  "reason": "Brief explanation",
  "should_continue": true/false
}

