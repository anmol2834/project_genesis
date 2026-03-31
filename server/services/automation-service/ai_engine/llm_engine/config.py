"""
LLM Engine — Config
====================
LLM execution parameters loaded from shared config.
All values come from server/.env via GlobalConfig.

Never hardcode API keys or model names here.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMConfig:
    """Immutable LLM execution config."""
    api_key:         str
    model:           str
    timeout_seconds: int
    max_retries:     int
    temperature:     float = 0.0    # Strict determinism
    top_p:           float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty:  float = 0.0


def get_llm_config() -> LLMConfig:
    """
    Load LLM config from shared GlobalConfig.
    Falls back to env vars directly if config is unavailable.
    """
    try:
        from shared.config import get_config
        cfg = get_config()
        return LLMConfig(
            api_key=cfg.OPENAI_API_KEY,
            model=cfg.OPENAI_MODEL,
            timeout_seconds=cfg.OPENAI_TIMEOUT_SECONDS,
            max_retries=cfg.OPENAI_MAX_RETRIES,
        )
    except Exception:
        # Fallback for isolated testing
        return LLMConfig(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            timeout_seconds=int(os.getenv("OPENAI_TIMEOUT_SECONDS", "30")),
            max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "2")),
        )
