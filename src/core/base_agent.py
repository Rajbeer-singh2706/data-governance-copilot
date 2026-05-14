from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
import time

from core.logging_utils import setup_logger


@dataclass
class AgentRequest:
    query: str                        # ← the raw NL question
    intent: str = ""                  # ← set by Supervisor after classification
    context: Dict[str, Any] = field( # ← extra data for write operations
        default_factory=dict
    )
    filters: Dict[str, Any] = field( # ← optional query filters
        default_factory=dict
    )
    query_id: str = field(           # ← auto-generated unique ID
        default_factory=lambda: str(uuid.uuid4())[:8]
    )
    time_range: Optional[str] = None # ← "last_month", "Q3_2024"
    data_products: List[str] = field(# ← ["retention", "cac"]
        default_factory=list
    )

@dataclass
class AgentResult:
    agent_name: str           # which agent produced this
    success: bool             # did it work?
    data: Any = None          # raw payload — dict, list, anything
    summary: str = ""         # human-readable explanation (for LLM)
    error: Optional[str]=None # error message if success=False
    sources: List[str] = field(default_factory=list)
                              # e.g. ["Collibra DGC: Retention Metric"]
    confidence: float = 1.0   # 0.0–1.0 (mock=0.85, live=0.95)
    execution_time_ms: float = 0.0
    metadata: Dict[str,Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )

    def to_dict(self) -> Dict:   # serialise for API response
        return {
            "agent":            self.agent_name,
            "success":          self.success,
            "summary":          self.summary,
            "data":             self.data,
            "error":            self.error,
            "sources":          self.sources,
            "confidence":       self.confidence,
            "execution_time_ms":self.execution_time_ms,
            "metadata":         self.metadata,
            "timestamp":        self.timestamp,
        }

class BaseAgent(ABC):
    name: str = "base_agent"        # overridden by each subclass
    description: str = "Base agent"
    capabilities: List[str] = []

    def __init__(self, config=None, enable_mock: bool = True):
        self.config      = config
        self.enable_mock = enable_mock
        self.logger = setup_logger(f"agent.{self.name}")  # named logger
        self._healthy    = True

    def execute(self, request: AgentRequest) -> AgentResult:
        """Public entry point — NEVER overridden by subclasses."""
        import time
        start = time.time()
        self.logger.info(
            f"[{request.query_id}] {self.name} received: "
            f"'{request.query[:80]}'"
        )
        try:
            result = self._execute(request)         # call subclass logic
            result.execution_time_ms = round(
                (time.time() - start) * 1000, 2
            )
            self.logger.info(
                f"[{request.query_id}] {self.name} done in "
                f"{result.execution_time_ms}ms"
            )
            return result
        except Exception as e:
            self.logger.error(
                f"[{request.query_id}] {self.name} failed: {e}",
                exc_info=True
            )
            return AgentResult(      # never raises — always returns
                agent_name = self.name,
                success    = False,
                error      = str(e),
                summary    = f"{self.name} error: {e}",
                execution_time_ms = round(
                    (time.time() - start) * 1000, 2
                ),
            )

    @abstractmethod
    def _execute(self, request: AgentRequest) -> AgentResult:
        """Subclasses implement THIS — not execute()."""
        pass

    def health_check(self) -> Dict[str, Any]:
        return {
            "agent":        self.name,
            "healthy":      self._healthy,
            "mock_mode":    self.enable_mock,
            "capabilities": self.capabilities,
        }
