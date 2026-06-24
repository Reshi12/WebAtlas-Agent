"""Provider-agnostic LLM interface with two-tier (cheap/strong) support.

Supports:
  - Groq (via ``groq`` SDK)
  - Google Gemini (via ``google-generativeai`` SDK)
  - OpenAI-compatible (covers OpenAI, Nemotron via NIM, GLM, etc.)

Config-driven provider selection via config.yaml; API keys via .env.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Protocol, runtime_checkable

from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


# ── Protocol ─────────────────────────────────────────────────────────────────


@runtime_checkable
class LLMProvider(Protocol):
    """Any LLM backend must satisfy this interface."""

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=20))
    def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        json_mode: bool = False,
        temperature: float | None = None,
    ) -> str:
        """Send a chat-completion request and return the assistant's text."""
        ...


# ── Concrete providers ───────────────────────────────────────────────────────


class GroqProvider:
    """Groq cloud LLM provider."""

    def __init__(self, api_key: str, model: str, default_temperature: float = 0.1):
        try:
            from groq import Groq
        except ImportError as exc:
            raise ImportError("groq package required: pip install groq") from exc
        self.client = Groq(api_key=api_key)
        self.model = model
        self.default_temperature = default_temperature
        self._total_tokens = 0

