"""Base agent contract — AgentRequest, AgentResult, BaseAgent."""
from __future__ import annotations

import time
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
    context: Dict[str, Any] = field(default_factory=dict)
    intent: Optional[str] = None
    query_id: Optional[str] = None


@dataclass
class AgentResult:
    success: bool
    data: Optional[Any] = None
    message: str = ""
    confidence: float = 0.0
    sources: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    intent: Optional[str] = None
    query_id: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0

    @property
    def summary(self) -> str:
        """Alias for message — backward compatibility."""
        return self.message

    @property
    def error(self) -> str:
        """Error string — returns message if it contains error info, else first error."""
        if self.message and not self.success:
            return self.message
        return self.errors[0] if self.errors else ""

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

    def health_check(self) -> Dict[str, Any]:
        """Basic liveness check — subclasses can override."""
        try:
            req = AgentRequest(query="health check")
            t0 = time.monotonic()
            result = self.execute(req)
            elapsed = (time.monotonic() - t0) * 1000
            return {
                "agent": self.name,
                "healthy": result.success,
                "status": "ok" if result.success else "degraded",
                "latency_ms": round(elapsed, 2),
            }
        except Exception as exc:
            return {"agent": self.name, "healthy": False, "status": "error", "error": str(exc)}

