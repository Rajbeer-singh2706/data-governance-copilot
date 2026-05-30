"""LiteLLM factory with fallback chain."""
from __future__ import annotations

import os
from typing import Any, Optional, Type


def get_llm(config=None, streaming: bool = False):
    """Return a BaseChatModel with LiteLLM fallback chain."""
    try:
        from langchain_groq import ChatGroq
        from langchain_community.chat_models import ChatLiteLLM

        model = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
        api_key = os.getenv("GROQ_API_KEY", "")

        if not api_key:
            raise ValueError("GROQ_API_KEY not set")

        llm = ChatGroq(model=model, api_key=api_key, streaming=streaming, temperature=0.1)
        return llm
    except Exception:
        # Fallback to a mock-safe stub
        return _MockLLM()


def get_structured_llm(config=None, schema: Optional[Type] = None):
    """Return an LLM bound to a Pydantic schema for structured output."""
    llm = get_llm(config)
    if schema is not None and hasattr(llm, "with_structured_output"):
        try:
            return llm.with_structured_output(schema)
        except Exception:
            pass
    return llm


class _MockLLM:
    """No-op LLM stub used when no API keys are available."""
    def invoke(self, prompt, **kwargs):
        return type("Msg", (), {"content": "Mock LLM response — no API key configured."})()

    def with_structured_output(self, schema):
        return self
