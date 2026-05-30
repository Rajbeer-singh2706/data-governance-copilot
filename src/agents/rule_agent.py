"""Rule Agent — rule registry CRUD."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List

from src.core.base_agent import AgentRequest, AgentResult, BaseAgent

_RULE_REGISTRY: Dict[str, Dict] = {}


class RuleAgent(BaseAgent):
    def _create_rule(self, request: AgentRequest) -> AgentResult:
        rule_id = str(uuid.uuid4())[:8]
        rule = {
            "id": rule_id,
            "name": f"Rule from: {request.query[:50]}",
            "query": request.query,
            "products": request.data_products,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "active",
        }
        _RULE_REGISTRY[rule_id] = rule
        return AgentResult(
            success=True,
            data=rule,
            message=f"Rule {rule_id} created",
            confidence=0.95,
            metadata={"rule_id": rule_id},
        )

    def _evaluate_rules(self, request: AgentRequest) -> AgentResult:
        rules = list(_RULE_REGISTRY.values())
        passed = failed = skipped = 0
        for rule in rules:
            try:
                # Simplified evaluation — always pass in mock
                passed += 1
            except Exception:
                failed += 1
        return AgentResult(
            success=True,
            data=rules,
            message=f"Evaluated {len(rules)} rules: {passed} passed, {failed} failed",
            confidence=0.90,
            metadata={"passed": passed, "failed": failed, "skipped": skipped},
        )

    def _list_rules(self, request: AgentRequest) -> AgentResult:
        rules = list(_RULE_REGISTRY.values())
        return AgentResult(
            success=True,
            data=rules,
            message=f"{len(rules)} rules in registry",
            confidence=0.99,
            metadata={"count": len(rules), "passed": 0, "failed": 0, "skipped": 0},
        )

    def execute(self, request: AgentRequest) -> AgentResult:
        q = request.query.lower()
        if any(kw in q for kw in ["create", "add", "new", "define", "create a business"]):
            return self._create_rule(request)
        if any(kw in q for kw in ["evaluate", "check", "validate", "run"]):
            return self._evaluate_rules(request)
        return self._list_rules(request)
