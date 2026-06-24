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
