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
        )

        history = list(state.get("step_history", []))
        history.append(step_record)

        tokens = dict(state.get("tokens_by_backend", {"agent_browser": 0, "webwright": 0}))
        tokens["webwright"] = tokens.get("webwright", 0) + getattr(llm.client, "total_tokens", 0)

        post_domain = state.get("page_domain", "")
        if post_url:
            try:
                post_domain = urlparse(post_url).netloc
            except Exception:
                pass

        return {
            "step_history": history,
            "tokens_by_backend": tokens,
            "page_url": post_url,
            "page_domain": post_domain,
            "error_message": error_msg,
        }

    return webwright_actor_node


def _build_search_query(user_task: str, step_task: str) -> str:
    """Build a search query without an extra LLM call."""
    combined = f"{user_task} {step_task}".strip()
    return combined[:200] if combined else step_task


def _is_synthesis_step(step_desc: str) -> bool:
    lowered = step_desc.lower()
    return any(
        word in lowered
        for word in ("synthesize", "summarize", "summary", "compile", "consolidate")
    )


def _latest_research_result(state: AgentState) -> str | None:
    for record in reversed(state.get("step_history", [])):
        if record.get("backend") != "webwright":
            continue
        if record.get("success") and record.get("result"):
            return record["result"]
    return None


def _collect_urls(query: str, max_pages: int) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()

    for url in _search_duckduckgo(query, max_pages):
        if url not in seen:
            seen.add(url)
            urls.append(url)

    return urls[:max_pages]


def _search_duckduckgo(query: str, limit: int) -> list[str]:
    try:
        import httpx
    except ImportError as exc:
        raise ImportError("httpx required: pip install httpx") from exc

    search_url = f"https://lite.duckduckgo.com/lite/?q={quote_plus(query)}"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; Browseragent/1.0)"}

    with httpx.Client(timeout=20, follow_redirects=True, headers=headers) as client:
        response = client.get(search_url)
        response.raise_for_status()
        html = response.text

    links = re.findall(
        r'uddg=([^&"]+)',
        html,
    )
    if links:
        from urllib.parse import unquote

        cleaned = []
        for link in links:
            url = unquote(link)
            if url.startswith("http") and "duckduckgo.com" not in url:
                cleaned.append(url)
                if len(cleaned) >= limit:
                    break
        if cleaned:
            return cleaned

    links = re.findall(
        r'class="result-link"[^>]*href="(https?://[^"]+)"',
        html,
    )
    if not links:
        links = re.findall(r'href="(https?://[^"]+)"', html)

    cleaned: list[str] = []
    for link in links:
        if "duckduckgo.com" in link:
            continue
        cleaned.append(link)
        if len(cleaned) >= limit:
            break
    return cleaned


def _fetch_pages(urls: list[str], timeout: float) -> list[dict[str, str]]:
    try:
        import httpx
    except ImportError as exc:
        raise ImportError("httpx required: pip install httpx") from exc

    headers = {"User-Agent": "Mozilla/5.0 (compatible; Browseragent/1.0)"}
    excerpts: list[dict[str, str]] = []

    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        for url in urls:
            try:
                response = client.get(url)
                if response.status_code >= 400:
                    continue
                text = _html_to_text(response.text)
                if len(text) < 100:
                    continue
                excerpts.append(
                    {
                        "url": str(response.url),
                        "title": _extract_title(response.text),
                        "text": text[:6000],
                    }
                )
            except Exception as exc:
                logger.debug("Failed to fetch %s: %s", url, exc)

    return excerpts


def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
