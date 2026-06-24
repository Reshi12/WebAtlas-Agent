"""Planner node — breaks a task into steps and routes each to a backend.

The planner is also a router: it tags each step with the backend best suited
to execute it (``agent_browser`` for deterministic actions, ``webwright`` for
open-ended research/exploration). This routing decision uses the cheap model
since it's a classification task, not a reasoning task.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from core.llm_provider import AgentLLM
from core.state import AgentState, PlanStep

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """\
You are a task planner for an autonomous browser agent. Your job is to break
down a user's task into a sequence of concrete, executable steps AND decide
which backend should execute each step.

## Backends

1. **agent_browser** — Use for interactive tasks requiring the actual browser:
   - Filling forms, quizzes, logging in, booking flows, add-to-cart actions
   - Any action where per-step safety interception is critical

2. **webwright** — Use for fast questions, research, and data gathering:
   - Comparing prices across multiple websites
   - Asking general questions where you don't need to show the browser
   - "Find the best X" or "Compare X across Y" tasks

## Rules
- Each step must be self-contained and executable by its assigned backend.
- Steps should be ordered logically (dependencies first).
- Be specific: "Search for iPhone 15 on amazon.in" not "Search for the product".
- If a task mixes research and action, split into research steps (webwright)
  followed by action steps (agent_browser).
- Never combine a research step with an action step in the same entry.

## Output Format
Return a JSON object with a "plan" key containing an array of step objects:
{
  "plan": [
    {"step": "description of what to do", "backend": "agent_browser"|"webwright", "details": "additional context"},
    ...
  ]
}
"""


def make_planner_node(llm: AgentLLM, config: dict[str, Any]):
    """Factory: creates the planner node function with closed-over LLM and config."""

    def planner_node(state: AgentState) -> dict[str, Any]:
        """Break the user's task into steps and assign backends."""
        task = state["task"]
        logger.info("Planning task: %s", task)

        messages = [
            {
                "role": "user",
                "content": f"Break this task into steps and assign backends:\n\n{task}",
            }
        ]

        response = llm.client.complete(
            system=PLANNER_SYSTEM_PROMPT,
            messages=messages,
            json_mode=True,
        )

        try:
            parsed = json.loads(response)
            raw_plan = parsed if isinstance(parsed, list) else parsed.get("plan", [])
        except (json.JSONDecodeError, KeyError, AttributeError, TypeError) as exc:
            logger.warning("Cheap model plan failed (%s), escalating to strong model", exc)
            response = llm.client.complete(
                system=PLANNER_SYSTEM_PROMPT,
                messages=messages,
                json_mode=True,
            )
            parsed = json.loads(response)
            raw_plan = parsed if isinstance(parsed, list) else parsed.get("plan", [])

        plan: list[PlanStep] = []
        for entry in raw_plan:
            plan.append(
                PlanStep(
                    step=entry.get("step", ""),
                    backend=entry.get("backend", "agent_browser"),
                    details=entry.get("details", ""),
                )
            )

        logger.info("Plan created with %d steps", len(plan))
        for i, s in enumerate(plan, 1):
            logger.info("  %d. [%s] %s", i, s["backend"], s["step"])

        return {
            "plan": plan,
            "current_step_index": 0,
            "retry_count": 0,
            "status": "running",
        }

    return planner_node


# ── Replanner ────────────────────────────────────────────────────────────────

REPLAN_SYSTEM_PROMPT = """\
You are replanning a task for an autonomous browser agent. A step has failed
repeatedly. Review the original plan, the step history (what was tried and
what went wrong), and produce a revised plan starting from the current point.

You may:
- Rephrase the failing step to be more specific
- Change the backend assignment (agent_browser ↔ webwright) if the current backend is a poor fit
- Insert additional preparatory steps
- Skip the step if it's no longer needed

Return the same JSON format: {"plan": [{"step": "...", "backend": "...", "details": "..."}, ...]}
Only include steps from the current point onward (already-completed steps
are handled separately).
"""


def make_replan_node(llm: AgentLLM, config: dict[str, Any]):
    """Factory: creates the replan node for recovering from repeated failures."""

    def replan_node(state: AgentState) -> dict[str, Any]:
        """Revise the plan after repeated failures on a step."""
        task = state["task"]
        current_idx = state.get("current_step_index", 0)
        plan = state.get("plan", [])
        history = state.get("step_history", [])
        error = state.get("error_message", "Unknown error")

        current_step = plan[current_idx] if current_idx < len(plan) else {"step": "unknown"}

