"""Safety gate node — backend-agnostic payment/login/personal-info detection.

Runs after EVERY action from EITHER backend (agent-browser or Webwright).
This is the single enforcement point for all safety rules — neither backend
can be a loophole because the gate lives outside both in the graph.

Two detection layers:
  Layer 1 — Fast keyword/domain check (no LLM call)
  Layer 2 — LLM confirmation (only when Layer 1 is ambiguous)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from core.llm_provider import AgentLLM
from core.state import AgentState, PageClassification
from safety.payment_keywords import (
    check_destructive_action,
    check_payment_text,
    check_payment_url,
    detect_personal_info_fields,
    load_safety_keywords,
)
from safety.rules import enforce_safety_gate

logger = logging.getLogger(__name__)

SAFETY_CLASSIFICATION_PROMPT = """\
You are a safety classifier for a browser automation agent. Analyze the
provided page snapshot and URL to determine if this is a payment page,
login page, or contains personal information fields.

## Classification Rules
- Payment page: any page where the user is expected to enter payment
  details (card number, CVV, UPI ID, net banking, EMI, etc.) or confirm
  a financial transaction. Includes checkout pages, order confirmation
  with payment, Razorpay/Stripe/PayU embedded forms.
- Login page: any page with username/email + password fields for
  authentication. NOT search forms, NOT signup forms (unless they also
  require login credentials).
- Personal info fields: form fields asking for name, email, phone,
  address, DOB, ID numbers, etc. List them.

## Output Format (JSON only)
{
  "is_payment_page": true/false,
  "is_login_page": true/false,
  "has_personal_info_fields": true/false,
  "personal_info_field_labels": ["Name", "Phone", ...],
  "other_field_labels": ["Search query", "Quantity", ...],
  "reason": "Brief explanation of classification"
}
"""


def make_safety_gate_node(llm: AgentLLM, config: dict[str, Any]):
    """Factory: creates the safety gate node."""

    keywords = load_safety_keywords(config)

    def safety_gate_node(state: AgentState) -> dict[str, Any]:
        """Classify the current page and enforce safety rules.

        Returns a partial state update. If unsafe, sets interrupt fields
        that will cause the graph to route to human_interrupt_node.
        """
        page_url = state.get("page_url", "")
        page_snapshot = state.get("page_snapshot", "")
        page_domain = state.get("page_domain", "")

        logger.info("[safety_gate] Checking page: %s", page_url)

        # ── Layer 1: Fast keyword check (no LLM) ────────────────────────
        url_match = check_payment_url(
            page_url,
            keywords["payment_url_keywords"],
            keywords["payment_domains"],
        )
        text_match = check_payment_text(
            page_snapshot,
            keywords["payment_text_keywords"],
        )

        # Clear match → skip LLM
        if url_match and text_match:
            logger.info("[safety_gate] Layer 1: PAYMENT detected (URL + text match)")
            classification = PageClassification(
                is_payment_page=True,
                is_login_page=False,
                has_personal_info_fields=False,
                agent_fillable_fields=[],
                human_required_fields=[],
                reason=f"Payment page — URL contains payment keywords, "
                       f"text contains payment-related fields. Domain: {page_domain}",
            )
            return enforce_safety_gate(state, classification)

        # Clear negative — no URL match and no text match
        if not url_match and not text_match and not _might_have_form_fields(page_snapshot):
