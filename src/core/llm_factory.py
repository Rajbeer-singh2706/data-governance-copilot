"""
src/core/llm_factory.py
Day 14: LiteLLM-backed LLM factory with automatic multi-provider fallback.

Drop-in replacement for ChatOpenAI — same .invoke() / .stream() interface.

Fallback chain (from LLMConfig.fallback_models):
  gpt-4o  →  gpt-4o-mini  →  anthropic/claude-haiku-4-5  →  gemini/gemini-1.5-flash

LiteLLM automatically tries the next model when it hits:
  • API errors (5xx)
  • Timeout errors
  • Rate limit errors (429)
  • Model availability issues

Usage — replaces ChatOpenAI everywhere:
    from core.llm_factory import get_llm
    from config.settings import config

    llm = get_llm(config.llm)
    result = llm.invoke("your prompt")
"""
from __future__ import annotations

import logging
import os

from langchain_community.chat_models import ChatLiteLLM
from langchain_core.language_models import BaseChatModel

from config.settings import LLMConfig

logger = logging.getLogger(__name__)


def get_llm(config: LLMConfig, streaming: bool = False) -> BaseChatModel:
    """
    Return a LangChain-compatible LLM with automatic fallback routing.

    Args:
        config:    LLMConfig from AppConfig — contains primary_model + fallbacks
        streaming: If True, enables token streaming (for synthesizer_node)

    Returns:
        BaseChatModel with .with_fallbacks() chained — same interface as ChatOpenAI
    """
    primary = ChatLiteLLM(
        model       = config.primary_model,
        temperature = config.temperature,
        max_tokens  = config.max_tokens,
        timeout     = config.timeout,
        max_retries = config.max_retries,
        streaming   = streaming,
    )

    if not config.fallback_models:
        return primary

    fallbacks = [
        ChatLiteLLM(
            model       = m,
            temperature = config.temperature,
            max_tokens  = config.max_tokens,
            timeout     = config.timeout,
        )
        for m in config.fallback_models
    ]

    logger.debug(
        "LLM chain: %s → %s",
        config.primary_model,
        " → ".join(config.fallback_models),
    )
    return primary.with_fallbacks(fallbacks)


def get_structured_llm(config: LLMConfig, schema) -> BaseChatModel:
    """
    Return an LLM bound to a Pydantic schema for structured output.

    Used by:
      • intent.py  — classify_intent_gpt() returns IntentClassification
      • Any agent needing typed LLM output

    Note: Uses primary_model only (no fallback) because structured output
    requires consistent schema support. gpt-4o always supports it.
    """
    base = ChatLiteLLM(
        model       = config.primary_model,
        temperature = 0,                 # must be 0 for deterministic classification
        max_tokens  = config.max_tokens,
        timeout     = config.timeout,
        max_retries = config.max_retries,
    )
    return base.with_structured_output(schema)