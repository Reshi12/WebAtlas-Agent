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

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=20))
    def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        json_mode: bool = False,
        temperature: float | None = None,
    ) -> str:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}] + messages,
            "temperature": temperature if temperature is not None else self.default_temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = self.client.chat.completions.create(**kwargs)
        if response.usage:
            self._total_tokens += response.usage.total_tokens
        return response.choices[0].message.content or ""

    @property
    def total_tokens(self) -> int:
        return self._total_tokens


class GeminiProvider:
    """Google Gemini LLM provider."""

    def __init__(self, api_key: str, model: str, default_temperature: float = 0.1):
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise ImportError(
                "google-genai package required: pip install google-genai"
            ) from exc
        self.client = genai.Client(api_key=api_key)
        self.model_name = model
        self.default_temperature = default_temperature
        self._total_tokens = 0
        self.types = types

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=20))
    def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        json_mode: bool = False,
        temperature: float | None = None,
    ) -> str:
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(
                self.types.Content(
                    role=role, 
                    parts=[self.types.Part.from_text(text=msg["content"])]
                )
            )

        config = self.types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature if temperature is not None else self.default_temperature,
            response_mime_type="application/json" if json_mode else "text/plain",
        )
        
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=config,
        )

        if hasattr(response, "usage_metadata") and response.usage_metadata:
            self._total_tokens += getattr(response.usage_metadata, "total_token_count", 0)
        return response.text or ""

    @property
    def total_tokens(self) -> int:
        return self._total_tokens


class OpenAICompatibleProvider:
    """OpenAI-compatible provider (OpenAI, Nemotron via NIM, GLM, etc.)."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        default_temperature: float = 0.1,
    ):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError("openai package required: pip install openai") from exc
        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = OpenAI(**client_kwargs)
        self.model = model
        self.default_temperature = default_temperature
        self._total_tokens = 0

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=20))
    def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        json_mode: bool = False,
        temperature: float | None = None,
    ) -> str:
