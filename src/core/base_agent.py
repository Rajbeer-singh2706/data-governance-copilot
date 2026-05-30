"""Base agent contract — AgentRequest, AgentResult, BaseAgent."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentRequest:
    query: str
    thread_id: str = "default"
    user_id: str = "anonymous"
    time_range: str = "last_30_days"
    data_products: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    success: bool
    data: Optional[Any] = None
    message: str = ""
    confidence: float = 0.0
    sources: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    @classmethod
    def failure(cls, message: str, error: str = "") -> "AgentResult":
        return cls(success=False, message=message, errors=[error] if error else [])


class BaseAgent(ABC):
    """Abstract base for all agents."""

    @abstractmethod
    def execute(self, request: AgentRequest) -> AgentResult:
        """Execute the agent logic."""

    @property
    def name(self) -> str:
        return self.__class__.__name__
