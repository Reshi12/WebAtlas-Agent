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
