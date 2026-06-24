"""Research actor node — web research via HTTP fetch + the main LLM.

Uses the same API key/provider as the rest of the agent (config.yaml + .env).
No external webwright CLI or separate model config files.
"""

from __future__ import annotations

import json
import logging
import os
import re
from html import unescape
from typing import Any
from urllib.parse import quote_plus, urlparse

from core.llm_provider import AgentLLM
from core.state import AgentState, StepRecord
from safety.rules import is_awaiting_human

logger = logging.getLogger(__name__)

DEFAULT_NEWS_URLS = [
    "https://techcrunch.com/category/artificial-intelligence/",
    "https://www.theverge.com/ai-artificial-intelligence",
    "https://venturebeat.com/category/ai/",
    "https://news.google.com/search?q=AI+news&hl=en-US&gl=US&ceid=US:en",
]

SYNTHESIS_SYSTEM_PROMPT = """\
You are a research assistant. Synthesize the provided web page excerpts into a
clear, accurate answer for the user's task. Cite sources by site name when possible.
If the excerpts are insufficient, say what is missing. Return plain text, not JSON.
"""


def make_webwright_actor_node(
    llm: AgentLLM,
    config: dict[str, Any],
):
    """Factory: creates the research (webwright backend) node."""

    ww_cfg = config.get("webwright", {})
    output_base = ww_cfg.get("output_dir", "logs")
    max_pages = int(ww_cfg.get("max_pages", 5))
    page_timeout = float(ww_cfg.get("page_timeout_seconds", 20))

    def webwright_actor_node(state: AgentState) -> dict[str, Any]:
        """Execute a research step via HTTP fetch + main LLM."""

        if is_awaiting_human(state):
            logger.warning("webwright_actor called while awaiting human — skipping")
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
        user_task = state.get("task", "")

        full_task = step_desc
        if details:
            full_task += f"\n\nAdditional context: {details}"

        logger.info("[webwright] Executing step %d: %s", idx + 1, step_desc)

        # Synthesis-only steps reuse the previous successful research result.
        if _is_synthesis_step(step_desc):
            prior = _latest_research_result(state)
            if prior:
                step_record = StepRecord(
                    step=step_desc,
                    backend="webwright",
                    action=f"synthesize prior research: {full_task[:100]}",
                    result=prior[:2000],
                    success=True,
                    attempt=state.get("retry_count", 0) + 1,
                    tokens_used=0,
                )
                history = list(state.get("step_history", []))
                history.append(step_record)
                return {"step_history": history, "error_message": None}

        step_output_dir = os.path.join(output_base, task_id, f"webwright_step{idx + 1}")
        os.makedirs(step_output_dir, exist_ok=True)

        if dry_run:
            step_record = StepRecord(
                step=step_desc,
                backend="webwright",
                action=f"[dry-run] research: {full_task[:100]}",
                result="Dry run — no execution",
                success=True,
                attempt=state.get("retry_count", 0) + 1,
                tokens_used=0,
            )
            history = list(state.get("step_history", []))
            history.append(step_record)
            return {"step_history": history}

        result_text = ""
        success = False
        error_msg = None
        post_url = state.get("page_url", "")

        try:
            query = _build_search_query(user_task, full_task)
            urls = _collect_urls(query, max_pages)

            if not urls:
                error_msg = "No URLs found for research query"
                result_text = error_msg
            else:
                excerpts = _fetch_pages(urls, page_timeout)
                if not excerpts:
                    error_msg = "Could not fetch content from search results"
                    result_text = error_msg
                else:
                    result_text = _synthesize(llm, user_task, full_task, excerpts)
                    success = True
                    post_url = excerpts[0]["url"]
                    _save_research_log(step_output_dir, query, excerpts, result_text)

        except Exception as exc:
            error_msg = str(exc)
            logger.error("[webwright] %s", error_msg)
            result_text = error_msg

        step_record = StepRecord(
            step=step_desc,
            backend="webwright",
            action=f"research: {full_task[:100]}",
            result=result_text[:2000],
            success=success,
            attempt=state.get("retry_count", 0) + 1,
            tokens_used=getattr(llm.client, "total_tokens", 0),
