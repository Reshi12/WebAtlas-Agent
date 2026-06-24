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
        refs = snapshot_data.get("refs", {})

        # ── 2. Get current URL ───────────────────────────────────────────
        current_url = browser.get_url()
        domain = ""
        try:
            domain = urlparse(current_url).netloc
        except Exception:
            pass

        # ── 3. Ask LLM to pick an action ────────────────────────────────
        context = (
            f"## Current Step\n{step_desc}\n\n"
            f"## Additional Context\n{details}\n\n"
            f"## Current URL\n{current_url}\n\n"
            f"## Page Snapshot (interactive elements)\n{snapshot_text}\n\n"
            f"## Available Refs\n{json.dumps(refs, indent=2)}"
        )

        messages = [{"role": "user", "content": context}]

        # Start with cheap model; escalate if needed
        model = llm.client
        used_strong = False
        try:
            response = model.complete(
                system=ACTION_SYSTEM_PROMPT,
                messages=messages,
                json_mode=True,
            )
            action_data = json.loads(response)
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("Cheap model failed (%s), escalating to strong", exc)
            model = llm.client
            used_strong = True
            response = model.complete(
                system=ACTION_SYSTEM_PROMPT,
                messages=messages,
                json_mode=True,
            )
            action_data = json.loads(response)

        action = action_data.get("action", "")
        ref = action_data.get("ref", "")
        value = action_data.get("value", "")
        reasoning = action_data.get("reasoning", "")

        logger.info(
            "[agent_browser] Action: %s %s %s — %s",
            action, ref, value, reasoning,
        )

        # ── 4. Execute action (or dry-run) ───────────────────────────────
        if dry_run:
            action_result = {"success": True, "data": {"dry_run": True}}
            logger.info("[DRY RUN] Would execute: %s %s %s", action, ref, value)
        else:
            action_result = _execute_action(browser, action, ref, value)

        # ── 5. Wait for page to settle ───────────────────────────────────
        if not dry_run and action_result.get("success"):
            browser.wait()

        # ── 6. Re-snapshot for safety gate ───────────────────────────────
        post_snapshot = ""
        post_url = current_url
        if not dry_run:
            post_url = browser.get_url()
            post_snap = browser.snapshot()
            if post_snap.get("success"):
                post_snapshot = post_snap.get("data", {}).get("snapshot", "")

        # ── 7. Build step record ─────────────────────────────────────────
        step_record = StepRecord(
            step=step_desc,
            backend="agent_browser",
            action=f"{action} {ref} {value}".strip(),
            result=json.dumps(action_result.get("data", {})),
            success=action_result.get("success", False),
            attempt=state.get("retry_count", 0) + 1,
            tokens_used=0,
        )

        # ── 8. Save screenshot ───────────────────────────────────────────
        screenshot_path = None
        if not dry_run and config.get("logging", {}).get("screenshots", True):
            ts = datetime.now(timezone.utc).strftime("%H%M%S")
            ss_filename = f"step{idx + 1}_{action}_{ts}.png"
            from core.persistence import save_screenshot

            try:
                ss_result = browser.screenshot(
                    f"logs/{task_id}/screenshots/{ss_filename}"
                )
                if ss_result.get("success"):
                    screenshot_path = f"logs/{task_id}/screenshots/{ss_filename}"
                    step_record["screenshot_path"] = screenshot_path
            except Exception as exc:
                logger.debug("Screenshot failed: %s", exc)

        # Update step history
        history = list(state.get("step_history", []))
        history.append(step_record)

        # Update token tracking
        tokens = dict(state.get("tokens_by_backend", {"agent_browser": 0, "webwright": 0}))
        tokens["agent_browser"] = tokens.get("agent_browser", 0) + getattr(model, "total_tokens", 0)

        post_domain = ""
        try:
            post_domain = urlparse(post_url).netloc
        except Exception:
            pass

        return {
            "page_url": post_url,
            "page_domain": post_domain,
            "page_snapshot": post_snapshot,
            "step_history": history,
            "used_strong_model_this_step": used_strong,
            "tokens_by_backend": tokens,
            "last_action_screenshot": screenshot_path,
            "error_message": None if action_result.get("success") else action_result.get("error"),
        }

    return agent_browser_actor_node


def _execute_action(
    browser: BrowserSession, action: str, ref: str, value: str
) -> dict[str, Any]:
    """Dispatch a parsed action to the right BrowserSession method."""
    action = action.lower().strip()

    try:
        if action == "click":
            return browser.click(ref)
        elif action == "fill":
            return browser.fill(ref, value)
        elif action == "select":
            return browser.select(ref, value)
        elif action == "check":
            return browser.check(ref)
        elif action == "type":
            return browser.type_text(ref, value)
        elif action == "press":
            return browser.press(value)
        elif action == "scroll":
            parts = value.split()
            direction = parts[0] if parts else "down"
            amount = int(parts[1]) if len(parts) > 1 else 3
            return browser.scroll(direction, amount)
        elif action == "goto":
            return browser.goto(value)
        elif action == "back":
            return browser.back()
        else:
            logger.warning("Unknown action '%s', attempting as click", action)
            return browser.click(ref)
    except Exception as exc:
        logger.error("Action execution failed: %s", exc)
        return {"success": False, "error": str(exc)}
