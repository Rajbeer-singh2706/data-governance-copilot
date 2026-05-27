import uuid
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.base_agent import BaseAgent, AgentRequest, AgentResult

# ── Rule Registry (in-memory — replace with DB in production) ──
RULE_REGISTRY: Dict[str, Dict] = {
    "DQ-001": {
        "id":         "DQ-001",
        "name":       "Retention Completeness Check",
        "type":       "data_quality",
        "dimension":  "completeness",
        "asset":      "analytics.retention_metrics",
        "expression": "null_count / total_count < 0.01",
        "threshold":  0.01,
        "severity":   "High",
        "enabled":    True,
        "owner":      "Data Engineering",
        "created":    "2024-01-15",
    },
    "DQ-002": {
        "id":         "DQ-002",
        "name":       "Retention Rate Range Validity",
        "type":       "data_quality",
        "dimension":  "validity",
        "asset":      "analytics.retention_metrics",
        "expression": "gross_retention_rate BETWEEN 0 AND 100",
        "threshold":  None,
        "severity":   "Critical",
        "enabled":    True,
        "owner":      "Data Engineering",
        "created":    "2024-01-15",
    },
    "BR-001": {
        "id":         "BR-001",
        "name":       "GRR Minimum Threshold Alert",
        "type":       "business_rule",
        "dimension":  None,
        "asset":      "retention",
        "expression": "gross_retention_rate >= 85",
        "threshold":  85.0,
        "severity":   "High",
        "enabled":    True,
        "owner":      "Customer Success",
        "created":    "2024-03-10",
    },
    "BR-002": {
        "id":         "BR-002",
        "name":       "CAC Payback Period Ceiling",
        "type":       "business_rule",
        "dimension":  None,
        "asset":      "cac",
        "expression": "payback_period_months <= 20",
        "threshold":  20,
        "severity":   "Medium",
        "enabled":    True,
        "owner":      "Marketing Analytics",
        "created":    "2024-04-22",
    },
}


# ── Rule Agent ───────────────────────────────────────────────
class RuleAgent(BaseAgent):
    """
    Creates and manages DQ and business rules.
    Three operations: create, list, evaluate.
    Wired in the Supervisor as on-demand only.
    """
    name         = "rule_agent"
    description  = "Creates and manages DQ and business rules"
    capabilities = [
        "rule_creation",
        "rule_listing",
        "rule_evaluation",
        "dq_rule_management",
        "business_rule_management",
    ]

    def __init__(self, config=None, enable_mock: bool = True):
        super().__init__(config, enable_mock)

    def _execute(self, request: AgentRequest) -> AgentResult:
        q = request.query.lower()

        if any(kw in q for kw in [
            "create rule", "add rule", "define rule",
            "new rule", "create dq", "create a rule",
            "create a business", "create a dq",
        ]):
            return self._create_rule(request)

        elif any(kw in q for kw in [
            "evaluate", "check rules", "run rules",
            "validate rules",
        ]):
            # FIX: evaluate must be checked BEFORE list because
            # "evaluate all rules" contains "all rules" which
            # previously matched the list branch first.
            return self._evaluate_rules(request)

        elif any(kw in q for kw in [
            "list rules", "show rules", "what rules",
            "all rules", "existing rules",
        ]):
            return self._list_rules(request)

        else:
            return self._list_rules(request)

    def _create_rule(self,
                     request: AgentRequest) -> AgentResult:
        context   = request.context
        rule_type = "data_quality"
        if any(kw in request.query.lower()
               for kw in ["business rule", "threshold", "kpi"]):
            rule_type = "business_rule"

        prefix  = "DQ" if rule_type == "data_quality" else "BR"
        rule_id = f"{prefix}-{str(uuid.uuid4())[:4].upper()}"

        new_rule = {
            "id":         rule_id,
            "name":       context.get(
                "rule_name",
                f"Rule: {request.query[:60]}"
            ),
            "type":       rule_type,
            "dimension":  context.get("dimension",
                                       "completeness"),
            "asset":      context.get(
                "asset",
                request.data_products[0]
                if request.data_products else "unknown"
            ),
            "expression": context.get("expression",
                                       "user_defined"),
            "threshold":  context.get("threshold"),
            "severity":   context.get("severity", "Medium"),
            "enabled":    True,
            "owner":      context.get("owner",
                                       "Data Governance"),
            "created":    datetime.utcnow().date().isoformat(),
        }

        RULE_REGISTRY[rule_id] = new_rule
        self.logger.info(
            f"Rule created: {rule_id} ({new_rule['name']})"
        )

        return AgentResult(
            agent_name = self.name,
            success    = True,
            summary    = (
                f"✅ Rule **{rule_id}** created: "
                f"_{new_rule['name']}_\n"
                f"  Type: {rule_type} | "
                f"Severity: {new_rule['severity']} | "
                f"Asset: {new_rule['asset']}"
            ),
            data       = new_rule,
            sources    = ["Rule Registry"],
            confidence = 1.0,
            metadata   = {
                "rule_id":   rule_id,
                "rule_type": rule_type,
            },
        )

    def _list_rules(self,
                    request: AgentRequest) -> AgentResult:
        products = request.data_products or []
        rules    = list(RULE_REGISTRY.values())

        if products:
            rules = [
                r for r in rules
                if any(p in r.get("asset", "")
                       for p in products)
            ]

        dq_rules = [r for r in rules
                    if r["type"] == "data_quality"]
        br_rules = [r for r in rules
                    if r["type"] == "business_rule"]

        parts = [f"📋 **Rule Registry** ({len(rules)} total)"]
        if dq_rules:
            parts.append(
                f"\n**Data Quality Rules ({len(dq_rules)}):**"
            )
            for r in dq_rules:
                enabled = "✅" if r.get("enabled") else "⏸️"
                parts.append(
                    f"  {enabled} **{r['id']}** "
                    f"[{r.get('dimension','—')}] "
                    f"{r['name']} → {r['asset']}"
                )

        if br_rules:
            parts.append(
                f"\n**Business Rules ({len(br_rules)}):**"
            )
            for r in br_rules:
                enabled = "✅" if r.get("enabled") else "⏸️"
                thresh  = r.get("threshold", "N/A")
                parts.append(
                    f"  {enabled} **{r['id']}** "
                    f"{r['name']} "
                    f"(threshold: {thresh})"
                )

        if not rules:
            parts.append("No rules found for this scope.")

        return AgentResult(
            agent_name = self.name,
            success    = True,
            summary    = "\n".join(parts),
            data       = rules,
            sources    = ["Rule Registry"],
            confidence = 1.0,
            metadata   = {"total_rules": len(rules)},
        )

    def _evaluate_rules(self,
                        request: AgentRequest) -> AgentResult:
        products = request.data_products or []
        rules    = list(RULE_REGISTRY.values())
        if products:
            rules = [
                r for r in rules
                if any(p in r.get("asset", "")
                       for p in products)
            ]

        results = []
        for rule in rules:
            # Mock: 70% pass rate
            # Production: execute SQL against Databricks
            passed = random.random() > 0.3
            results.append({
                "rule_id":   rule["id"],
                "rule_name": rule["name"],
                "type":      rule["type"],
                "passed":    passed,
                "severity":  rule["severity"],
                "message":   "✅ Passed" if passed
                             else "❌ Failed",
            })

        failed = [r for r in results if not r["passed"]]
        lines  = [
            f"📋 **Rule Evaluation** ({len(rules)} rules)"
        ]
        for r in results:
            icon = "✅" if r["passed"] else "❌"
            lines.append(
                f"  {icon} **{r['rule_id']}**: {r['rule_name']}"
            )
        if failed:
            lines.append(
                f"\n⚠️ **{len(failed)} rule(s) failed** "
                f"— review required."
            )
        else:
            lines.append("\n✅ All rules passed.")

        return AgentResult(
            agent_name = self.name,
            success    = True,
            summary    = "\n".join(lines),
            data       = results,
            sources    = ["Rule Registry"],
            confidence = 0.85,
            metadata   = {
                "passed": len(results) - len(failed),
                "failed": len(failed),
            },
        )