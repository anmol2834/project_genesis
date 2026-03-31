"""
LLM Engine — OpenAI Client
===========================
Thin async wrapper around the OpenAI Python SDK.

Responsibilities:
  - Manage the AsyncOpenAI client singleton (one per process).
  - Expose a single call: chat_completion(system, user, config) → raw text.
  - Handle OpenAI-specific errors and surface them as LLMClientError.
  - Never log full prompt content (PII risk).

The client is intentionally thin — all retry/timeout logic lives in executor.py.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from .config import LLMConfig

logger = logging.getLogger(__name__)

_openai_client = None


def get_openai_client(api_key: str):
    """Return the singleton AsyncOpenAI client. Created on first call."""
    global _openai_client
    if _openai_client is None:
        try:
            from openai import AsyncOpenAI
            _openai_client = AsyncOpenAI(api_key=api_key)
            logger.info("OpenAI async client initialised.")
        except ImportError as exc:
            raise LLMClientError("openai package not installed. Run: pip install openai>=1.30.0") from exc
    return _openai_client


async def chat_completion(
    system_prompt: str,
    user_prompt: str,
    config: LLMConfig,
    max_tokens: int = 300,
) -> tuple[str, int, int]:
    """
    Call the OpenAI chat completions API.

    Args:
        system_prompt: System role content.
        user_prompt:   User role content.
        config:        LLMConfig with model, temperature, etc.
        max_tokens:    Max completion tokens (from policy constraints).

    Returns:
        (raw_text, prompt_tokens, completion_tokens)

    Raises:
        LLMClientError: On API errors, auth failures, or timeouts.
    """
    if not config.api_key:
        raise LLMClientError("OPENAI_API_KEY is not set. Add it to server/.env.")

    client = get_openai_client(config.api_key)

    try:
        response = await client.chat.completions.create(
            model=config.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=config.temperature,
            top_p=config.top_p,
            frequency_penalty=config.frequency_penalty,
            presence_penalty=config.presence_penalty,
            max_tokens=max_tokens,
            timeout=config.timeout_seconds,
        )

        raw_text         = response.choices[0].message.content or ""
        prompt_tokens    = response.usage.prompt_tokens if response.usage else 0
        completion_tokens = response.usage.completion_tokens if response.usage else 0

        # Log token usage without logging prompt content
        logger.debug(
            "OpenAI call complete",
            extra={
                "model":              config.model,
                "prompt_tokens":      prompt_tokens,
                "completion_tokens":  completion_tokens,
                "finish_reason":      response.choices[0].finish_reason,
            },
        )

        return raw_text, prompt_tokens, completion_tokens

    except Exception as exc:
        # Mask the exception message in case it contains prompt fragments
        exc_type = type(exc).__name__
        raise LLMClientError(f"OpenAI API error ({exc_type}): {_safe_error_msg(exc)}") from exc


def _safe_error_msg(exc: Exception) -> str:
    """Extract a safe error message that won't leak prompt content."""
    msg = str(exc)
    # Truncate long messages that might contain prompt fragments
    return msg[:200] if len(msg) > 200 else msg


class LLMClientError(Exception):
    """Raised on OpenAI client errors (auth, rate limit, timeout, etc.)."""
    pass
