"""Payment/login/personal-info keyword and domain lists for the safety gate.

These are the Layer-1 (fast, no-LLM) detection lists. Layer-2 LLM confirmation
is handled in ``core/nodes/safety_gate.py`` and only fires when Layer 1 is
ambiguous.
"""

from __future__ import annotations

from typing import Any


def load_safety_keywords(config: dict[str, Any]) -> dict[str, Any]:
    """Load all keyword lists from config.yaml's ``safety`` block.

    Returns a dict with normalised (lowercased) keyword sets for fast
    ``in`` checks.
    """
    safety = config.get("safety", {})

    return {
        "payment_url_keywords": {
            kw.lower() for kw in safety.get("payment_url_keywords", [])
        },
        "payment_domains": {
