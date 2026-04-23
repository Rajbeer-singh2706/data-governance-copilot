"""
Base agent class. All specialized agents inherit from this.
Defines the standard interface: execute(), health_check(), and metadata.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid

from core.logging_utils import setup_logger, logger


@dataclass
class AgentResult:
    """Standardized result object returned by every agent."""
    agent_name: str
    success: bool
    data: Any = None
    summary: str = ""
    error: Optional[str] = None
    sources: List[str] = field(default_factory=list)
    confidence: float = 1.0          # 0.0–1.0
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict:
        return {
            "agent": self.agent_name,
            "success": self.success,
            "summary": self.summary,
            "data": self.data,
            "error": self.error,
            "sources": self.sources,
            "confidence": self.confidence,
            "execution_time_ms": self.execution_time_ms,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class AgentRequest:
    """Input structure for all agent calls."""
    query: str
    intent: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    filters: Dict[str, Any] = field(default_factory=dict)
    query_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    time_range: Optional[str] = None          # e.g. "last_month", "Q3_2024"
    data_products: List[str] = field(default_factory=list)


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the Data Governance Copilot.

    Responsibilities:
    - Define a uniform execute() interface
    - Provide shared logging, error wrapping, and health-check boilerplate
    - Let subclasses focus purely on their domain logic
    """

    name: str = "base_agent"
    description: str = "Base agent"
    capabilities: List[str] = []

    def __init__(self, config=None, enable_mock: bool = True):
        self.config = config
        self.enable_mock = enable_mock
        self.logger = setup_logger(f"agent.{self.name}")
        self._healthy = True

    def execute(self, request: AgentRequest) -> AgentResult:
        """
        Public entry point. Wraps _execute() with timing, logging, and error handling.
        """
        import time
        start = time.time()
        self.logger.info(f"[{request.query_id}] {self.name} received: '{request.query[:80]}'")

        try:
            result = self._execute(request)
            result.execution_time_ms = round((time.time() - start) * 1000, 2)
            self.logger.info(
                f"[{request.query_id}] {self.name} completed in {result.execution_time_ms}ms "
                f"| success={result.success} confidence={result.confidence:.2f}"
            )
            return result
        except Exception as e:
            duration = round((time.time() - start) * 1000, 2)
            self.logger.error(f"[{request.query_id}] {self.name} failed: {e}", exc_info=True)
            return AgentResult(
                agent_name=self.name,
                success=False,
                error=str(e),
                summary=f"{self.name} encountered an error: {str(e)}",
                execution_time_ms=duration,
            )

    @abstractmethod
    def _execute(self, request: AgentRequest) -> AgentResult:
        """Domain-specific logic to be implemented by each specialized agent."""
        pass

    def health_check(self) -> Dict[str, Any]:
        """Return current health status of this agent and its dependencies."""
        return {
            "agent": self.name,
            "healthy": self._healthy,
            "mock_mode": self.enable_mock,
            "capabilities": self.capabilities,
        }

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self.name} mock={self.enable_mock}>"
