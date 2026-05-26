"""
src/core/llm_factory.py
Day 14: LLM factory with multi-provider support.

Supports two backends (controlled by LLM_PROVIDER env var):
  • "groq"   — ChatGroq (fast, free tier available)
  • "openai" — ChatLiteLLM with automatic multi-provider fallback

Fallback chain when provider=openai (from LLMConfig.fallback_models):
  gpt-4o  →  gpt-4o-mini  →  anthropic/claude-haiku-4-5  →  gemini/gemini-1.5-flash

Usage:
    from core.llm_factory import get_llm, get_structured_llm
    from config.settings import config

    llm = get_llm(config.llm)
    result = llm.invoke("your prompt")
"""
from __future__ import annotations

import logging
import os

from langchain_core.language_models import BaseChatModel
from config.settings import LLMConfig

logger = logging.getLogger(__name__)


def _build_groq_llm(config: LLMConfig, streaming: bool = False) -> BaseChatModel:
    """Build a ChatGroq instance."""
    from langchain_groq import ChatGroq

    api_key = config.api_key or os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set in environment or LLMConfig.")

    # Strip provider prefix if present (e.g. "groq/llama-3.3-70b-versatile" → "llama-3.3-70b-versatile")
    model_name = config.primary_model
    if "/" in model_name:
        model_name = model_name.split("/", 1)[1]

    return ChatGroq(
        groq_api_key=api_key,
        model_name=model_name,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        streaming=streaming,
    )


def _build_litellm_llm(config: LLMConfig, streaming: bool = False) -> BaseChatModel:
    """Build a ChatLiteLLM instance with fallback chain."""
    from langchain_litellm import ChatLiteLLM

    primary = ChatLiteLLM(
        model=config.primary_model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        timeout=config.timeout,
        max_retries=config.max_retries,
        streaming=streaming,
    )

    if not config.fallback_models:
        return primary

    fallbacks = [
        ChatLiteLLM(
            model=m,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            timeout=config.timeout,
        )
        for m in config.fallback_models
    ]

    logger.debug(
        "LLM chain: %s → %s",
        config.primary_model,
        " → ".join(config.fallback_models),
    )
    return primary.with_fallbacks(fallbacks)


def get_llm(config: LLMConfig, streaming: bool = False) -> BaseChatModel:
    """
    Return a LangChain-compatible LLM.

    Provider is determined by config.provider (LLM_PROVIDER env var):
      • "groq"   → ChatGroq (recommended for dev — fast + free tier)
      • "openai" → ChatLiteLLM with fallback chain

    Args:
        config:    LLMConfig from AppConfig
        streaming: If True, enables token streaming (for synthesizer_node)

    Returns:
        BaseChatModel — same .invoke() / .stream() interface regardless of provider
    """
    provider = (config.provider or "openai").lower()

    try:
        if provider == "groq":
            llm = _build_groq_llm(config, streaming=streaming)
            logger.info("LLM backend: Groq / %s", config.primary_model)
            return llm
        else:
            llm = _build_litellm_llm(config, streaming=streaming)
            logger.info("LLM backend: LiteLLM / %s", config.primary_model)
            return llm
    except Exception as exc:
        logger.error("Failed to build LLM (%s): %s", provider, exc)
        raise


def get_structured_llm(config: LLMConfig, schema) -> BaseChatModel:
    """
    Return an LLM bound to a Pydantic schema for structured output.

    Used by:
      • intent.py  — classify_intent_gpt() returns IntentClassification
      • Any agent needing typed LLM output

    Note: Uses primary_model only (no fallback) because structured output
    requires consistent schema support.

    IMPORTANT: Returns the LLM itself — caller must chain with prompt:
        chain = prompt | get_structured_llm(config, MySchema)
        result = chain.invoke({"query": "..."})
    """
    provider = (config.provider or "openai").lower()

    try:
        if provider == "groq":
            base = _build_groq_llm(config, streaming=False)
        else:
            from langchain_litellm import ChatLiteLLM
            base = ChatLiteLLM(
                model=config.primary_model,
                temperature=0,   # must be 0 for deterministic structured output
                max_tokens=config.max_tokens,
                timeout=config.timeout,
                max_retries=config.max_retries,
            )

        logger.info(
            "Structured LLM: provider=%s model=%s schema=%s",
            provider,
            config.primary_model,
            schema.__name__ if hasattr(schema, "__name__") else str(schema),
        )
        # THIS IS THE CRITICAL FIX — .with_structured_output() was missing
        return base.with_structured_output(schema)

    except Exception as exc:
        logger.error("Failed to build structured LLM (%s): %s", provider, exc)
        raise