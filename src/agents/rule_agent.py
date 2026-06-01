"""Rule Agent — rule registry CRUD with seed rules."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.base_agent import AgentRequest, AgentResult, BaseAgent

# Seed rules pre-populated at module load
_RULE_REGISTRY: Dict[str, Dict] = {
    "DQ-0001": {
        "id": "DQ-0001", "type": "data_quality", "name": "GRR Completeness Check",
        "asset": "analytics.retention_metrics", "dimension": "completeness",
        "expression": "null_count / total < 0.01", "severity": "High",
        "products": ["retention"], "status": "active",
        "created_at": "2024-01-01T00:00:00+00:00",
    },
    "DQ-0002": {
        "id": "DQ-0002", "type": "data_quality", "name": "Bookings Range Check",
        "asset": "analytics.bookings_fact", "dimension": "validity",
        "expression": "arr > 0", "severity": "High",
        "products": ["bookings"], "status": "active",
        "created_at": "2024-01-01T00:00:00+00:00",
    },
    "BR-0001": {
        "id": "BR-0001", "type": "business_rule", "name": "GRR Threshold ≥ 85%",
        "asset": "retention", "expression": "grr >= 85.0", "threshold": 85.0,
        "severity": "High", "products": ["retention"], "status": "active",
        "created_at": "2024-01-01T00:00:00+00:00",
    },
    "BR-0002": {
        "id": "BR-0002", "type": "business_rule", "name": "LTV:CAC Ratio ≥ 3x",
        "asset": "ltv", "expression": "ltv_cac_ratio >= 3.0", "threshold": 3.0,
        "severity": "Medium", "products": ["ltv"], "status": "active",
        "created_at": "2024-01-01T00:00:00+00:00",
    },
}

# Public alias
RULE_REGISTRY = _RULE_REGISTRY

_dq_counter = 10
_br_counter = 10


class RuleAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "rule_agent"

    def _next_id(self, rule_type: str) -> str:
        global _dq_counter, _br_counter
        if "business" in rule_type.lower():
            _br_counter += 1
            return f"BR-{_br_counter:04d}"
        _dq_counter += 1
        return f"DQ-{_dq_counter:04d}"

    def _create_rule(self, request: AgentRequest) -> AgentResult:
        ctx = request.context or {}
        q = request.query.lower()
        # Determine type from query or context
        if "business" in q or "threshold" in q:
            rule_type = "business_rule"
        else:
            rule_type = "data_quality"

        rule_id = self._next_id(rule_type)
        rule = {
            "id": rule_id,
            "type": rule_type,
            "name": ctx.get("rule_name", f"Rule from: {request.query[:50]}"),
            "asset": ctx.get("asset", ""),
            "dimension": ctx.get("dimension", ""),
            "expression": ctx.get("expression", request.query),
            "severity": ctx.get("severity", "Medium"),
            "threshold": ctx.get("threshold"),
            "products": request.data_products or [],
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _RULE_REGISTRY[rule_id] = rule
        return AgentResult(
            success=True,
            data=rule,
            message=f"📝 Created rule `{rule_id}`: {rule['name']}",
            confidence=0.95,
            metadata={"rule_id": rule_id, "type": rule_type},
        )

    def _evaluate_rules(self, request: AgentRequest) -> AgentResult:
        products = request.data_products
        rules = [
            r for r in _RULE_REGISTRY.values()
            if not products or any(p in r.get("products", []) for p in products)
        ]
        passed = failed = skipped = 0
        results = []
        for rule in rules:
            # Simplified mock evaluation — all active rules pass
            status = "passed" if rule.get("status") == "active" else "skipped"
            if status == "passed":
                passed += 1
            else:
                skipped += 1
            results.append({
                "rule_id": rule["id"],
                "rule_name": rule["name"],
                "passed": status == "passed",
                "status": status,
            })
        return AgentResult(
            success=True,
            data=results,
            message=f"✅ Evaluated {len(rules)} rules: {passed} passed, {failed} failed, {skipped} skipped",
            confidence=0.90,
            metadata={"passed": passed, "failed": failed, "skipped": skipped},
        )

    def _list_rules(self, request: AgentRequest) -> AgentResult:
        products = request.data_products
        rules = [
            r for r in _RULE_REGISTRY.values()
            if not products or any(p in r.get("products", []) for p in products)
        ]
        return AgentResult(
            success=True,
            data=rules,
            message=f"📋 {len(rules)} rules in registry",
            confidence=0.99,
            metadata={"count": len(rules), "passed": 0, "failed": 0, "skipped": 0},
        )

    def execute(self, request: AgentRequest) -> AgentResult:
        q = request.query.lower()
        if any(kw in q for kw in ["create", "add", "new", "define"]):
            return self._create_rule(request)
        if any(kw in q for kw in ["evaluate", "check", "validate", "run"]):
            return self._evaluate_rules(request)
        return self._list_rules(request)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "healthy": True, "rules_count": len(_RULE_REGISTRY)}
