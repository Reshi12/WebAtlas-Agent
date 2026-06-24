"""agent-browser actor node — wraps agent-browser CLI for deterministic actions.

Each action is one subprocess call to the agent-browser CLI with ``--json``
for structured parsing. The loop per step:

    1. snapshot -i --json  → get current interactive elements as @eN refs
    2. LLM picks the right @eN ref + action for this step's intent
    3. Execute: fill/click/select/check/type via agent-browser
    4. Wait for page to settle (networkidle / --text / --url)
    5. Re-snapshot → refs are stale after any page change

The node returns the action taken + result so the safety gate can inspect
the post-action page state.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from core.browser_session import BrowserSession
from core.llm_provider import AgentLLM
from core.state import AgentState, StepRecord
from safety.rules import is_awaiting_human

logger = logging.getLogger(__name__)

ACTION_SYSTEM_PROMPT = """\
You are an action selector for a browser automation agent. Given the current
page snapshot (accessibility tree with @eN element references) and the step
to execute, decide what action to take.

## Available Actions
- click @eN — Click an interactive element
- fill @eN "value" — Fill a text input with a value
- select @eN "value" — Select a dropdown option
- check @eN — Toggle a checkbox
- type @eN "text" — Type text keystroke-by-keystroke
- press Key — Press a key (Enter, Tab, Escape, ArrowDown, etc.)
- scroll down/up N — Scroll the page (N = number of viewport heights)
- goto "url" — Navigate to a URL directly
- back — Go back in history

## Rules
- Use the @eN references from the snapshot — they are the only reliable way
  to target elements.
- Pick the SINGLE most appropriate action to advance toward the step goal.
- If the needed element isn't visible, scroll to find it first.
- NEVER interact with payment fields (card number, CVV, UPI, etc.).
- NEVER fill personal info fields (name, email, phone, address, etc.)
  — those will be handled by human handoff.

## Output Format (JSON)
{
  "action": "click",
  "ref": "@e12",
  "value": "",
  "reasoning": "Clicking the 'Add to Cart' button to add the selected item"
}

For scroll/press/goto/back, use ref="" and put the argument in value:
{"action": "press", "ref": "", "value": "Enter", "reasoning": "..."}
{"action": "goto", "ref": "", "value": "https://...", "reasoning": "..."}
{"action": "scroll", "ref": "", "value": "down 3", "reasoning": "..."}
"""


def make_agent_browser_actor_node(
    llm: AgentLLM,
    browser: BrowserSession,
    config: dict[str, Any],
):
    """Factory: creates the agent-browser actor node."""

    def agent_browser_actor_node(state: AgentState) -> dict[str, Any]:
        """Execute a single action via agent-browser based on the current step."""

        # Defense-in-depth: never act while awaiting human
        if is_awaiting_human(state):
            logger.warning("agent_browser_actor called while awaiting human — skipping")
            return {}

        plan = state.get("plan", [])
        idx = state.get("current_step_index", 0)
        if idx >= len(plan):
            return {"error_message": "No more steps to execute"}

        current_step = plan[idx]
        step_desc = current_step["step"]
        details = current_step.get("details", "")
        dry_run = state.get("dry_run", False)
        task_id = state.get("task_id", "unknown")

        logger.info("[agent_browser] Executing step %d: %s", idx + 1, step_desc)

        # ── 1. Get snapshot ──────────────────────────────────────────────
        snapshot_result = browser.snapshot()
        if not snapshot_result.get("success"):
            error = snapshot_result.get("error", "Snapshot failed")
            logger.error("Snapshot failed: %s", error)
            return {
                "error_message": f"Snapshot failed: {error}",
                "page_snapshot": "",
            }

        snapshot_data = snapshot_result.get("data", {})
        snapshot_text = snapshot_data.get("snapshot", "")
