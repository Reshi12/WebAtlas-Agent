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

Set should_continue to false if, despite success, you detect the task
cannot proceed further (e.g. out of stock, page removed, etc.).
"""


def make_verifier_node(llm: AgentLLM, config: dict[str, Any]):
    """Factory: creates the verifier node."""

    max_retries = config.get("safety", {}).get("max_retries", 2)

    def verifier_node(state: AgentState) -> dict[str, Any]:
        """Verify whether the last step succeeded and decide next routing."""

        plan = state.get("plan", [])
        idx = state.get("current_step_index", 0)
        history = state.get("step_history", [])
        page_snapshot = state.get("page_snapshot", "")
        page_url = state.get("page_url", "")
        retry_count = state.get("retry_count", 0)

        if not history:
            logger.warning("[verifier] No step history — nothing to verify")
            return {"error_message": "No step history to verify"}

        last_step = history[-1]
        step_desc = last_step.get("step", "")
        action = last_step.get("action", "")
        result = last_step.get("result", "")

        # If the step already reported failure at the action level
        if not last_step.get("success", True):
            logger.info("[verifier] Step reported failure at action level")
            return _handle_failure(
                state, retry_count, max_retries,
                f"Action failed: {last_step.get('result', 'unknown error')}",
            )

        # ── Ask LLM to verify ───────────────────────────────────────────
        context = (
            f"## Step\n{step_desc}\n\n"
            f"## Action Taken\n{action}\n\n"
            f"## Action Result\n{result[:1500]}\n\n"
            f"## Current Page URL\n{page_url}\n\n"
            f"## Current Page State\n{page_snapshot[:3000]}\n"
        )
