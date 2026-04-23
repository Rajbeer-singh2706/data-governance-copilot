"""
Rule Agent
----------
Creates and manages business rules and data quality rules.

WRITE capabilities:
- Define new DQ rules (completeness, accuracy, freshness, referential integrity)
- Register business rules in the governance catalog
- Trigger rule evaluations and return results
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from core.base_agent import BaseAgent, AgentRequest, AgentResult
from core.logging_utils import logger


# ---------------------------------------------------------------------------
# In-memory rule registry (replace with DB / Collibra in production)
# ---------------------------------------------------------------------------

RULE_REGISTRY: Dict[str, Dict] = {
    "DQ-001": {
        "id": "DQ-001",
        "name": "Retention Completeness Check",
        "type": "data_quality",
        "dimension": "completeness",
        "asset": "analytics.retention_metrics",
        "expression": "COUNT(*) WHERE region IS NULL / COUNT(*) < 0.01",
        "threshold": 0.01,
        "severity": "High",
        "enabled": True,
        "owner": "Data Engineering",
        "created": "2024-01-15",
    },
    "DQ-002": {
        "id": "DQ-002",
        "name": "Retention Rate Range Validity",
        "type": "data_quality",
        "dimension": "validity",
        "asset": "analytics.retention_metrics",
        "expression": "gross_retention_rate BETWEEN 0 AND 100",
        "threshold": None,
        "severity": "Critical",
        "enabled": True,
        "owner": "Data Engineering",
        "created": "2024-01-15",
    },
    "BR-001": {
        "id": "BR-001",
        "name": "GRR Minimum Threshold Alert",
        "type": "business_rule",
        "dimension": None,
        "asset": "retention",
        "expression": "gross_retention_rate >= 85",
        "threshold": 85.0,
        "severity": "High",
        "enabled": True,
        "owner": "Customer Success",
        "created": "2024-03-10",
    },
    "BR-002": {
        "id": "BR-002",
        "name": "CAC Payback Period Ceiling",
        "type": "business_rule",
        "dimension": None,
        "asset": "cac",
        "expression": "payback_period_months <= 20",
        "threshold": 20,
        "severity": "Medium",
        "enabled": True,
        "owner": "Marketing Analytics",
        "created": "2024-04-22",
    },
}


class RuleAgent(BaseAgent):
    """
    Business and Data Quality Rule management agent.

    Capabilities:
    - List and query existing rules
    - Create new DQ rules (completeness, accuracy, validity, freshness, uniqueness)
    - Create business rules with thresholds
    - Evaluate rules against current metric values
    - Enable / disable rules
    """

    name = "rule_agent"
    description = "Creates and manages business and data quality rules"
    capabilities = [
        "rule_listing",
        "dq_rule_creation",
        "business_rule_creation",
        "rule_evaluation",
        "rule_management",
    ]

    RULE_TYPE_KEYWORDS = {
        "data_quality": ["completeness", "accuracy", "timeliness", "validity", "uniqueness", "freshness", "dq rule", "data quality rule"],
        "business_rule": ["business rule", "threshold", "alert", "kpi rule", "metric rule"],
    }

    def _execute(self, request: AgentRequest) -> AgentResult:
        query_lower = request.query.lower()

        if any(kw in query_lower for kw in ["create rule", "add rule", "define rule", "new rule"]):
            return self._create_rule(request)
        elif any(kw in query_lower for kw in ["list rules", "show rules", "what rules", "all rules"]):
            return self._list_rules(request)
        elif any(kw in query_lower for kw in ["evaluate", "check rules", "run rules", "validate"]):
            return self._evaluate_rules(request)
        else:
            return self._list_rules(request)

    def _create_rule(self, request: AgentRequest) -> AgentResult:
        """Parse user intent and create a new rule."""
        query = request.query
        context = request.context

        # In production: use LLM to extract rule parameters from natural language
        rule_id = f"DQ-{str(uuid4())[:4].upper()}"
        rule_type = "data_quality"
        for rtype, keywords in self.RULE_TYPE_KEYWORDS.items():
            if any(kw in query.lower() for kw in keywords):
                rule_type = rtype
                break

        new_rule = {
            "id": rule_id,
            "name": context.get("rule_name", f"Auto-created rule: {query[:60]}"),
            "type": rule_type,
            "dimension": context.get("dimension", "completeness"),
            "asset": context.get("asset", request.data_products[0] if request.data_products else "unknown"),
            "expression": context.get("expression", "user_defined"),
            "threshold": context.get("threshold"),
            "severity": context.get("severity", "Medium"),
            "enabled": True,
            "owner": context.get("owner", "Data Governance Team"),
            "created": datetime.utcnow().date().isoformat(),
        }

        RULE_REGISTRY[rule_id] = new_rule
        logger.info(f"Rule created: {rule_id} ({new_rule['name']})")

        return AgentResult(
            agent_name=self.name,
            success=True,
            summary=f"✅ Rule **{rule_id}** created: _{new_rule['name']}_",
            data=new_rule,
            sources=["Rule Registry"],
            metadata={"rule_id": rule_id, "rule_type": rule_type},
        )

    def _list_rules(self, request: AgentRequest) -> AgentResult:
        products = request.data_products or []
        rules = list(RULE_REGISTRY.values())

        if products:
            rules = [r for r in rules if any(p in r.get("asset", "") for p in products)]

        summary = self._build_list_summary(rules)
        return AgentResult(
            agent_name=self.name,
            success=True,
            summary=summary,
            data=rules,
            sources=["Rule Registry"],
            metadata={"total_rules": len(rules)},
        )

    def _evaluate_rules(self, request: AgentRequest) -> AgentResult:
        """Simulate rule evaluation against current metric snapshot."""
        products = request.data_products or []
        rules = list(RULE_REGISTRY.values())
        if products:
            rules = [r for r in rules if any(p in r.get("asset", "") for p in products)]

        results = []
        for rule in rules:
            # Mock evaluation: randomly pass/fail for demo
            import random
            passed = random.random() > 0.3
            results.append({
                "rule_id": rule["id"],
                "rule_name": rule["name"],
                "passed": passed,
                "severity": rule["severity"],
                "message": "✅ Passed" if passed else f"❌ Failed — threshold violated",
            })

        failed = [r for r in results if not r["passed"]]
        summary_lines = [f"📋 **Rule Evaluation Results** ({len(rules)} rules)"]
        for r in results:
            icon = "✅" if r["passed"] else "❌"
            summary_lines.append(f"  {icon} {r['rule_id']}: {r['rule_name']}")
        if failed:
            summary_lines.append(f"\n⚠️ **{len(failed)} rule(s) failed** — review required.")

        return AgentResult(
            agent_name=self.name,
            success=True,
            summary="\n".join(summary_lines),
            data=results,
            sources=["Rule Registry"],
            metadata={"passed": len(results) - len(failed), "failed": len(failed)},
        )

    def _build_list_summary(self, rules: List[Dict]) -> str:
        if not rules:
            return "No rules found for the requested scope."
        dq_rules = [r for r in rules if r["type"] == "data_quality"]
        br_rules = [r for r in rules if r["type"] == "business_rule"]
        parts = [f"📋 **Rule Registry** ({len(rules)} total)"]
        if dq_rules:
            parts.append(f"\n**Data Quality Rules ({len(dq_rules)}):**")
            for r in dq_rules:
                enabled = "✅" if r.get("enabled") else "⏸️"
                parts.append(f"  {enabled} **{r['id']}** [{r['dimension']}] {r['name']} — {r['asset']}")
        if br_rules:
            parts.append(f"\n**Business Rules ({len(br_rules)}):**")
            for r in br_rules:
                enabled = "✅" if r.get("enabled") else "⏸️"
                parts.append(f"  {enabled} **{r['id']}** {r['name']} — threshold: {r.get('threshold', 'N/A')}")
        return "\n".join(parts)
