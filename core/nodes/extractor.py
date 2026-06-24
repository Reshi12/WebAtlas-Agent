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
