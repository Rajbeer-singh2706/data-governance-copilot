"""
Supervisor Agent (Orchestrator)
--------------------------------
The central brain of the Data Governance Copilot.

Responsibilities:
1. Parse natural language queries and classify intent
2. Determine which agents to invoke (and in what order)
3. Execute agents (with parallelism where possible)
4. Aggregate and reconcile responses
5. Generate a unified, business-friendly summary via LLM
6. Trigger write actions when required (tickets, metadata updates, rules)
"""

import json
import time
import concurrent.futures
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

from core.base_agent import AgentRequest, AgentResult, BaseAgent
from core.logging_utils import setup_logger, logger
from agents.information_agent import InformationAgent
from agents.knowledge_agent import KnowledgeAgent
from agents.metadata_agent import MetadataAgent
from agents.capacity_agent import CapacityAgent
from agents.rule_agent import RuleAgent


# ---------------------------------------------------------------------------
# Intent taxonomy
# ---------------------------------------------------------------------------

class QueryIntent(str, Enum):
    METRIC_ANALYSIS = "metric_analysis"          # "Why did retention drop?"
    DATA_QUALITY = "data_quality"                # "What's the DQ score for CAC?"
    GOVERNANCE = "governance"                    # "Who owns the bookings dataset?"
    INCIDENT_REVIEW = "incident_review"          # "Any open Jira issues for retention?"
    FULL_DIAGNOSTIC = "full_diagnostic"          # "Why did X happen?" — triggers all agents
    WRITE_TICKET = "write_ticket"                # "Create a bug for missing EU data"
    WRITE_METADATA = "write_metadata"            # "Update owner of retention metric"
    WRITE_RULE = "write_rule"                    # "Create a DQ rule for completeness"
    KNOWLEDGE_LOOKUP = "knowledge_lookup"        # "What is GRR?"
    UNKNOWN = "unknown"


INTENT_RULES = {
    # Write intents checked FIRST — more specific than read intents
    QueryIntent.WRITE_TICKET:     ["create ticket", "create a ticket", "open bug", "raise issue", "log incident", "create story", "create a bug", "file a ticket"],
    QueryIntent.WRITE_METADATA:   ["update owner", "set owner", "classify", "update metadata", "update description"],
    QueryIntent.WRITE_RULE:       ["create rule", "create a rule", "add rule", "define rule", "new rule", "create dq rule", "create a dq"],
    # Read intents
    QueryIntent.FULL_DIAGNOSTIC:  ["why did", "root cause", "investigate", "explain why", "diagnose", "what happened", "what caused"],
    QueryIntent.DATA_QUALITY:     ["data quality", "dq score", "completeness", "accuracy", "quality score", "data issue"],
    QueryIntent.GOVERNANCE:       ["who owns", "owner", "steward", "classification", "certified", "governance", "lineage"],
    QueryIntent.INCIDENT_REVIEW:  ["jira", "open bugs", "open issues", "blockers", "incidents", "stories", "bug tickets"],
    QueryIntent.KNOWLEDGE_LOOKUP: ["what is", "define ", "definition", "explain ", "meaning of", "what does", "how is"],
    QueryIntent.METRIC_ANALYSIS:  ["metric", "number", "value", "trend", "rate", "how much", "what is the", "show me"],
}

# Intent → agents to invoke
INTENT_AGENT_MAP: Dict[QueryIntent, List[str]] = {
    QueryIntent.FULL_DIAGNOSTIC:  ["information", "metadata", "capacity", "knowledge"],
    QueryIntent.METRIC_ANALYSIS:  ["information", "knowledge"],
    QueryIntent.DATA_QUALITY:     ["metadata", "information"],
    QueryIntent.GOVERNANCE:       ["metadata", "knowledge"],
    QueryIntent.INCIDENT_REVIEW:  ["capacity"],
    QueryIntent.WRITE_TICKET:     ["capacity"],
    QueryIntent.WRITE_METADATA:   ["metadata"],
    QueryIntent.WRITE_RULE:       ["rule"],
    QueryIntent.KNOWLEDGE_LOOKUP: ["knowledge", "metadata"],
    QueryIntent.UNKNOWN:          ["information", "knowledge"],
}


@dataclass
class SupervisorResponse:
    """Final aggregated response from the Supervisor Agent."""
    query: str
    intent: str
    final_summary: str
    agent_results: List[Dict] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)
    auto_created_tickets: List[str] = field(default_factory=list)
    data_products_referenced: List[str] = field(default_factory=list)
    overall_confidence: float = 0.0
    execution_time_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict:
        return {
            "query": self.query,
            "intent": self.intent,
            "final_summary": self.final_summary,
            "agent_results": self.agent_results,
            "recommended_actions": self.recommended_actions,
            "auto_created_tickets": self.auto_created_tickets,
            "data_products_referenced": self.data_products_referenced,
            "overall_confidence": self.overall_confidence,
            "execution_time_ms": self.execution_time_ms,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# LLM Synthesizer
# ---------------------------------------------------------------------------

class LLMSynthesizer:
    """
    Uses OpenAI / Azure OpenAI to generate the final business-friendly summary.
    Falls back to rule-based aggregation if LLM is unavailable.
    """

    SYSTEM_PROMPT = """You are a senior Data Governance Analyst assistant. 
Your job is to synthesize findings from multiple specialized agents (metrics, governance, 
Jira issues, knowledge base) into a clear, concise, business-friendly explanation.

Guidelines:
- Lead with the key finding (1-2 sentences)
- Use bullet points for supporting evidence
- Cite sources (data quality scores, Jira IDs, documentation references)
- End with specific, actionable next steps
- Tone: professional but conversational, avoid jargon
- Max length: 350 words
"""

    def __init__(self, config):
        self.config = config
        self._client = None
        self._init_client()

    def _init_client(self):
        try:
            if self.config.provider == "azure_openai":
                from openai import AzureOpenAI
                self._client = AzureOpenAI(
                    api_key=self.config.api_key,
                    azure_endpoint=self.config.azure_endpoint,
                    api_version=self.config.azure_api_version,
                )
                self._model = self.config.azure_deployment
            else:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.config.api_key)
                self._model = self.config.model
            logger.info(f"LLM client initialized: {self.config.provider} / {self._model}")
        except ImportError:
            logger.warning("OpenAI library not installed. Using rule-based synthesis.")

    def synthesize(self, query: str, intent: str, agent_summaries: List[str], anomalies: List[str]) -> str:
        if not self._client:
            return self._rule_based_synthesis(query, intent, agent_summaries, anomalies)

        agent_text = "\n\n".join(agent_summaries)
        anomaly_text = "\n".join(f"- {a}" for a in anomalies) if anomalies else "None detected."

        user_message = f"""
User Query: {query}
Detected Intent: {intent}

=== Agent Findings ===
{agent_text}

=== Detected Anomalies ===
{anomaly_text}

Please provide a unified, business-friendly summary with root cause analysis and next steps.
"""
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.2,
                max_tokens=500,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM synthesis failed: {e}")
            return self._rule_based_synthesis(query, intent, agent_summaries, anomalies)

    def _rule_based_synthesis(self, query: str, intent: str, summaries: List[str], anomalies: List[str]) -> str:
        """Deterministic fallback synthesis when LLM is unavailable."""
        parts = [f"## 🤖 Data Governance Copilot — Analysis Results\n"]
        parts.append(f"**Query:** _{query}_\n**Intent:** {intent}\n")
        parts.append("---\n")
        parts.extend(summaries)
        if anomalies:
            parts.append("\n---\n### ⚠️ Key Issues Detected:")
            parts.extend(f"- {a}" for a in anomalies)
        parts.append("\n---\n_Summary generated by rule-based engine (LLM unavailable)_")
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Supervisor Agent
# ---------------------------------------------------------------------------

class SupervisorAgent:
    """
    Orchestrates the full multi-agent pipeline for the Data Governance Copilot.
    """

    def __init__(self, config=None, enable_mock: bool = True):
        self.config = config
        self.enable_mock = enable_mock
        self.logger = setup_logger("supervisor")

        # Initialize all specialized agents
        self.agents: Dict[str, BaseAgent] = {
            "information": InformationAgent(config, enable_mock),
            "knowledge": KnowledgeAgent(config, enable_mock),
            "metadata": MetadataAgent(config, enable_mock),
            "capacity": CapacityAgent(config, enable_mock),
            "rule": RuleAgent(config, enable_mock),
        }

        # LLM synthesizer for final summary
        self.synthesizer = LLMSynthesizer(config.llm if config else type("C", (), {"provider": "none", "api_key": ""})())

        self.logger.info(f"SupervisorAgent initialized | mock={enable_mock} | agents={list(self.agents.keys())}")

    def run(self, query: str, time_range: Optional[str] = None, data_products: Optional[List[str]] = None) -> SupervisorResponse:
        """
        Main entry point: process a user query end-to-end.

        Steps:
        1. Classify intent
        2. Select relevant agents
        3. Execute agents (parallel where safe)
        4. Aggregate results
        5. Auto-create tickets for critical anomalies
        6. Synthesize final summary via LLM
        """
        start = time.time()
        import uuid
        query_id = str(uuid.uuid4())[:8]
        self.logger.info(f"[{query_id}] Processing query: '{query[:100]}'")

        # Step 1: Intent classification
        intent = self._classify_intent(query)
        self.logger.info(f"[{query_id}] Intent: {intent.value}")

        # Step 2: Extract data products
        extracted_products = data_products or self._extract_products(query)

        # Step 3: Build agent request
        request = AgentRequest(
            query=query,
            intent=intent.value,
            query_id=query_id,
            time_range=time_range,
            data_products=extracted_products,
        )

        # Step 4: Select and run agents
        agent_names = INTENT_AGENT_MAP.get(intent, ["information", "knowledge"])
        agent_results = self._run_agents_parallel(agent_names, request)

        # Step 5: Collect anomalies and auto-create tickets if needed
        all_anomalies = self._collect_anomalies(agent_results)
        auto_tickets = self._auto_create_tickets(all_anomalies, extracted_products)

        # Step 6: Build recommended actions
        actions = self._recommend_actions(intent, agent_results, all_anomalies)

        # Step 7: Synthesize final summary
        summaries = [r.summary for r in agent_results if r.success and r.summary]
        final_summary = self.synthesizer.synthesize(query, intent.value, summaries, all_anomalies)

        # Step 8: Compute overall confidence
        confidence_scores = [r.confidence for r in agent_results if r.success]
        overall_confidence = round(sum(confidence_scores) / len(confidence_scores), 2) if confidence_scores else 0.0

        execution_ms = round((time.time() - start) * 1000, 2)
        self.logger.info(f"[{query_id}] Completed in {execution_ms}ms | confidence={overall_confidence}")

        return SupervisorResponse(
            query=query,
            intent=intent.value,
            final_summary=final_summary,
            agent_results=[r.to_dict() for r in agent_results],
            recommended_actions=actions,
            auto_created_tickets=auto_tickets,
            data_products_referenced=extracted_products,
            overall_confidence=overall_confidence,
            execution_time_ms=execution_ms,
        )

    def _classify_intent(self, query: str) -> QueryIntent:
        """Rule-based intent classifier (replace with LLM in production)."""
        q = query.lower()
        for intent, keywords in INTENT_RULES.items():
            if any(kw in q for kw in keywords):
                return intent
        return QueryIntent.UNKNOWN

    def _extract_products(self, query: str) -> List[str]:
        """Identify data products mentioned in the query."""
        q = query.lower()
        product_keywords = {
            "retention": ["retention", "churn", "grr", "nrr"],
            "bookings": ["bookings", "arr", "mrr", "revenue"],
            "cac": ["cac", "acquisition cost", "payback"],
            "ltv": ["ltv", "lifetime value"],
        }
        found = [p for p, kws in product_keywords.items() if any(k in q for k in kws)]
        return found or ["retention"]

    def _run_agents_parallel(self, agent_names: List[str], request: AgentRequest) -> List[AgentResult]:
        """Run selected agents in parallel using a thread pool."""
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(agent_names)) as executor:
            future_map = {
                executor.submit(self.agents[name].execute, request): name
                for name in agent_names
                if name in self.agents
            }
            for future in concurrent.futures.as_completed(future_map, timeout=30):
                agent_name = future_map[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    self.logger.error(f"Agent {agent_name} raised an exception: {e}")
                    results.append(AgentResult(
                        agent_name=agent_name,
                        success=False,
                        error=str(e),
                        summary=f"{agent_name} failed: {e}",
                    ))
        return results

    def _collect_anomalies(self, results: List[AgentResult]) -> List[str]:
        anomalies = []
        for r in results:
            if r.success and isinstance(r.data, dict):
                anomalies.extend(r.data.get("anomalies", []))
                dq_issues = r.data.get("data_quality", {})
                if isinstance(dq_issues, dict):
                    for issue in dq_issues.get("issues", []):
                        if issue.get("severity") == "High":
                            anomalies.append(f"[DQ Issue] {issue.get('description', '')}")
        return anomalies

    def _auto_create_tickets(self, anomalies: List[str], products: List[str]) -> List[str]:
        """Auto-create Jira tickets for critical anomalies."""
        created = []
        capacity_agent: CapacityAgent = self.agents.get("capacity")
        if not capacity_agent:
            return created
        for anomaly in anomalies:
            if "threshold" in anomaly.lower() or "missing" in anomaly.lower() or "below" in anomaly.lower():
                product = products[0] if products else "unknown"
                result = capacity_agent.create_ticket_from_anomaly(anomaly, product)
                if result.success:
                    ticket_id = result.data.get("ticket_id", "UNKNOWN")
                    created.append(ticket_id)
                    self.logger.info(f"Auto-created ticket: {ticket_id}")
        return created

    def _recommend_actions(self, intent: QueryIntent, results: List[AgentResult], anomalies: List[str]) -> List[str]:
        actions = []
        if anomalies:
            actions.append("Review and resolve open data quality issues in Collibra.")
            actions.append("Assign at-risk accounts to CS team for proactive outreach.")
        if intent == QueryIntent.FULL_DIAGNOSTIC:
            actions.append("Schedule a data review meeting with the owning team.")
        for r in results:
            if not r.success:
                actions.append(f"Investigate {r.agent_name} connectivity — returned error: {r.error}")
        if not actions:
            actions.append("No immediate action required. Monitor KPIs on next refresh.")
        return actions

    def health_check(self) -> Dict[str, Any]:
        return {
            "supervisor": "healthy",
            "agents": {name: agent.health_check() for name, agent in self.agents.items()},
            "mock_mode": self.enable_mock,
            "timestamp": datetime.utcnow().isoformat(),
        }
