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
            d.lower() for d in safety.get("payment_domains", [])
        },
        "payment_text_keywords": {
            kw.lower() for kw in safety.get("payment_text_keywords", [])
        },
        "personal_info_fields": {
            f.lower() for f in safety.get("personal_info_fields", [])
        },
        "destructive_action_keywords": {
            kw.lower() for kw in safety.get("destructive_action_keywords", [])
        },
    }


# ── Standalone detection helpers (used by safety_gate_node) ──────────────────


def check_payment_url(url: str, keywords: set[str], domains: set[str]) -> bool:
    """Return True if the URL matches any payment keyword or domain."""
    url_lower = url.lower()

    # Check URL path segments
    for kw in keywords:
        if kw in url_lower:
            return True

    # Check domain
    from urllib.parse import urlparse

    try:
        domain = urlparse(url_lower).netloc
    except Exception:
        domain = ""

    for d in domains:
        if domain == d or domain.endswith("." + d):
            return True

    return False


def check_payment_text(snapshot_text: str, keywords: set[str]) -> bool:
    """Return True if the page snapshot contains payment-related text."""
    text_lower = snapshot_text.lower()
    matches = [kw for kw in keywords if kw in text_lower]
    # Require at least 2 keyword matches to reduce false positives
    return len(matches) >= 2


def detect_personal_info_fields(
