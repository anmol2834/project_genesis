"""
LLM Engine — Executor
======================
Orchestrates LLM execution with retry logic and timeout handling.

Flow:
  CompiledPrompt → chat_completion() → LLMResponse (raw text)

Retry logic:
  - Max 2 retries (configurable via OPENAI_MAX_RETRIES).
  - Exponential backoff: 1s, 2s.
  - Retries on: timeout, rate limit, server error (5xx).
  - Does NOT retry on: auth errors, invalid request errors.

Security:
  - Never logs full prompt content.
  - Masks API key in all log output.
  - Timeout enforced at client level.

Input:  CompiledPrompt (from prompt_compiler)
Output: LLMResponse (raw_text + token usage + latency)
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

from .config import get_llm_config, LLMConfig
from .client import chat_completion, LLMClientError
from ..prompt_compiler.schema import CompiledPrompt

logger = logging.getLogger(__name__)

# Errors that should NOT be retried
_NO_RETRY_ERRORS = (
    "AuthenticationError",
    "PermissionDeniedError",
    "InvalidRequestError",
    "BadRequestError",
)


@dataclass
class LLMResponse:
    """Raw response from the LLM provider."""
    raw_text:          str
    model_used:        str
    prompt_tokens:     int
    completion_tokens: int
    total_tokens:      int
    latency_ms:        float
    retry_count:       int = 0
    error:             Optional[str] = None


class LLMExecutionError(Exception):
    """Raised when the LLM call fails after all retries."""
    pass


class LLMExecutor:
    """
    Async LLM executor with retry and timeout handling.
    Stateless — safe to share across requests.
    Config is loaded once at construction.
    """

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        self._config = config or get_llm_config()

    async def execute(self, compiled_prompt: CompiledPrompt) -> LLMResponse:
        """
        Execute the compiled prompt against the LLM.

        Args:
            compiled_prompt: Output from the Prompt Compiler.

        Returns:
            LLMResponse with raw_text and token usage.

        Raises:
            LLMExecutionError: If all retries are exhausted.
        """
        max_tokens = self._resolve_max_tokens(compiled_prompt)
        return await self._with_retry(compiled_prompt, max_tokens)

    async def _with_retry(
        self,
        compiled_prompt: CompiledPrompt,
        max_tokens: int,
    ) -> LLMResponse:
        """Retry wrapper with exponential backoff."""
        last_error: Optional[str] = None
        retry_count = 0

        for attempt in range(self._config.max_retries + 1):
            try:
                return await self._call_provider(compiled_prompt, max_tokens, attempt)
            except LLMClientError as exc:
                error_msg = str(exc)
                last_error = error_msg

                # Don't retry auth/invalid request errors
                if any(no_retry in error_msg for no_retry in _NO_RETRY_ERRORS):
                    logger.error("LLM non-retryable error on attempt %d: %s", attempt + 1, type(exc).__name__)
                    raise LLMExecutionError(f"Non-retryable LLM error: {error_msg}") from exc

                retry_count += 1
                if attempt < self._config.max_retries:
                    backoff = 2 ** attempt   # 1s, 2s
                    logger.warning(
                        "LLM call failed (attempt %d/%d), retrying in %ds",
                        attempt + 1, self._config.max_retries + 1, backoff,
                    )
                    await asyncio.sleep(backoff)

        raise LLMExecutionError(
            f"LLM call failed after {self._config.max_retries + 1} attempts. "
            f"Last error: {last_error}"
        )

    async def _call_provider(
        self,
        compiled_prompt: CompiledPrompt,
        max_tokens: int,
        attempt: int,
    ) -> LLMResponse:
        """Make a single OpenAI API call and return LLMResponse."""
        start_ms = time.monotonic() * 1000

        raw_text, prompt_tokens, completion_tokens = await chat_completion(
            system_prompt=compiled_prompt.system_prompt,
            user_prompt=compiled_prompt.user_prompt,
            config=self._config,
            max_tokens=max_tokens,
        )

        latency_ms = (time.monotonic() * 1000) - start_ms

        logger.info(
            "LLM call succeeded",
            extra={
                "attempt":            attempt + 1,
                "model":              self._config.model,
                "prompt_tokens":      prompt_tokens,
                "completion_tokens":  completion_tokens,
                "latency_ms":         round(latency_ms, 1),
                "safe_mode":          compiled_prompt.is_safe_mode,
            },
        )

        return LLMResponse(
            raw_text=raw_text,
            model_used=self._config.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=round(latency_ms, 1),
            retry_count=attempt,
        )

    def _resolve_max_tokens(self, compiled_prompt: CompiledPrompt) -> int:
        """
        Resolve max_tokens from prompt metadata constraints.
        Falls back to a safe default if metadata is unavailable.
        """
        if compiled_prompt.metadata and compiled_prompt.metadata.constraints_applied:
            raw = compiled_prompt.metadata.constraints_applied.get("max_tokens")
            if raw is not None:
                try:
                    return max(50, min(int(raw), 1000))
                except (ValueError, TypeError):
                    pass
        # Safe default
        return 300
