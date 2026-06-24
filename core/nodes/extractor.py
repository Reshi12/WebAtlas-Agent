"""Crawl4AI wrapper — one-shot structured extraction from data-heavy pages.

Both agent-browser and Webwright backends can call this as a sub-tool when
a page needs clean structured extraction (e.g. a long results table) rather
than reading it row by row via the backend's own primitives.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def extract_page_data(
    url: str,
    extraction_schema: dict[str, Any] | None = None,
    css_selector: str | None = None,
) -> dict[str, Any]:
    """Extract structured data from a URL using Crawl4AI.

    Args:
        url: The page to extract from.
        extraction_schema: Optional JSON schema for structured extraction.
        css_selector: Optional CSS selector to narrow extraction scope.

    Returns:
        Dict with ``success``, ``content`` (markdown), ``extracted_data``
        (if schema provided), and ``metadata``.
    """
    try:
        from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
    except ImportError:
        logger.error("crawl4ai not installed: pip install crawl4ai")
        return {
            "success": False,
            "error": "crawl4ai not installed: pip install crawl4ai",
        }

    try:
        config_kwargs: dict[str, Any] = {}
        if css_selector:
            config_kwargs["css_selector"] = css_selector

        run_config = CrawlerRunConfig(**config_kwargs) if config_kwargs else None

        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(
                url=url,
                config=run_config,
            )

            output: dict[str, Any] = {
                "success": result.success,
                "content": result.markdown or "",
                "url": url,
                "metadata": {
                    "title": getattr(result, "title", ""),
                    "status_code": getattr(result, "status_code", None),
                },
            }

            # If an extraction schema was provided, try to apply it
            if extraction_schema and result.success:
                output["extracted_data"] = _apply_schema(
                    result.markdown or "", extraction_schema
                )

            return output

    except Exception as exc:
        logger.error("Crawl4AI extraction failed for %s: %s", url, exc)
        return {"success": False, "error": str(exc), "url": url}


def extract_page_data_sync(
    url: str,
    extraction_schema: dict[str, Any] | None = None,
    css_selector: str | None = None,
) -> dict[str, Any]:
    """Synchronous wrapper around ``extract_page_data``."""
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If there's already a running loop (e.g. inside LangGraph),
            # create a new one in a thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    extract_page_data(url, extraction_schema, css_selector),
                )
                return future.result(timeout=60)
        else:
            return loop.run_until_complete(
                extract_page_data(url, extraction_schema, css_selector)
            )
    except RuntimeError:
        return asyncio.run(
            extract_page_data(url, extraction_schema, css_selector)
        )


def _apply_schema(content: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Best-effort structured extraction against a schema.

    For now this is a simple field-matching pass. A more sophisticated
    implementation could use an LLM to map free-text content to the schema.
    """
    # Placeholder: return the content keyed under the schema's expected fields
    fields = schema.get("properties", schema.get("fields", {}))
    result: dict[str, Any] = {}
    for field_name in fields:
        # Simple heuristic: look for the field name in the content
        result[field_name] = None  # Would need LLM or regex to fill properly
    result["_raw_content"] = content[:5000]
    return result
