"""
FastAPI REST API for Data Governance Copilot
============================================
Exposes the multi-agent system as a REST API for:
- Microsoft Teams Bot integration
- Programmatic access
- Webhook callbacks
"""

import json
import time
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import uvicorn

from config.settings import config
from agents.supervisor_agent import SupervisorAgent
from core.logging_utils import setup_logger

logger = setup_logger("api")
app = FastAPI(
    title="Data Governance Copilot API",
    description="Multi-agent AI system for data governance, metrics, and operations.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# Dependency: lazy supervisor initialization
# ---------------------------------------------------------------------------

_supervisor: Optional[SupervisorAgent] = None

def get_supervisor() -> SupervisorAgent:
    global _supervisor
    if _supervisor is None:
        _supervisor = SupervisorAgent(config=config, enable_mock=config.enable_mock)
    return _supervisor


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=2000, description="Natural language query")
    time_range: Optional[str] = Field(None, description="e.g. last_month, Q3_2024")
    data_products: Optional[List[str]] = Field(None, description="e.g. ['retention', 'cac']")
    user_id: Optional[str] = Field(None, description="User identifier for audit logging")
    source: str = Field("api", description="Source system: api | teams | slack")

class TeamsActivityRequest(BaseModel):
    """Microsoft Teams Bot Framework activity format."""
    type: str
    text: Optional[str] = None
    from_: Optional[Dict] = Field(None, alias="from")
    channelId: Optional[str] = None
    conversation: Optional[Dict] = None

class CreateTicketRequest(BaseModel):
    summary: str
    description: str
    issue_type: str = "Bug"
    priority: str = "Medium"
    data_product: Optional[str] = None
    labels: Optional[List[str]] = None

class UpdateMetadataRequest(BaseModel):
    asset_name: str
    attribute: str
    value: str
    justification: Optional[str] = None

class CreateRuleRequest(BaseModel):
    rule_name: str
    rule_type: str  # data_quality | business_rule
    asset: str
    expression: str
    dimension: Optional[str] = None  # completeness, accuracy, etc.
    threshold: Optional[float] = None
    severity: str = "Medium"


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.get("/health", tags=["System"])
async def health_check(supervisor: SupervisorAgent = Depends(get_supervisor)):
    """Check system health and agent status."""
    return supervisor.health_check()


@app.post("/query", tags=["Core"])
async def process_query(
    request: QueryRequest,
    supervisor: SupervisorAgent = Depends(get_supervisor),
):
    """
    Main query endpoint. Processes natural language queries through the multi-agent system.
    Returns a unified analysis with metrics, governance insights, Jira issues, and recommendations.
    """
    start = time.time()
    logger.info(f"Query from {request.user_id or 'anonymous'} [{request.source}]: {request.query[:80]}")

    try:
        response = supervisor.run(
            query=request.query,
            time_range=request.time_range,
            data_products=request.data_products,
        )
        return {
            "status": "success",
            "data": response.to_dict(),
            "api_latency_ms": round((time.time() - start) * 1000, 2),
        }
    except Exception as e:
        logger.error(f"Query processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/teams/activity", tags=["Integrations"])
async def teams_activity(
    activity: TeamsActivityRequest,
    supervisor: SupervisorAgent = Depends(get_supervisor),
):
    """
    Microsoft Teams Bot Framework webhook handler.
    Accepts Bot Framework activity events and returns a response message.
    """
    if activity.type != "message" or not activity.text:
        return {"type": "message", "text": "Hello! Ask me anything about your data."}

    response = supervisor.run(query=activity.text.strip())
    return {
        "type": "message",
        "text": response.final_summary[:4000],  # Teams message limit
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": _build_adaptive_card(response),
            }
        ],
    }


@app.post("/tickets", tags=["Write Operations"])
async def create_ticket(
    request: CreateTicketRequest,
    supervisor: SupervisorAgent = Depends(get_supervisor),
):
    """Create a Jira ticket directly via the Capacity Agent."""
    from core.base_agent import AgentRequest
    agent_request = AgentRequest(
        query=f"create ticket: {request.summary}",
        context={
            "ticket_summary": request.summary,
            "ticket_description": request.description,
            "issue_type": request.issue_type,
            "priority": request.priority,
            "labels": request.labels or ["api-created"],
        },
        data_products=[request.data_product] if request.data_product else [],
    )
    capacity_agent = supervisor.agents["capacity"]
    result = capacity_agent.execute(agent_request)
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    return {"status": "success", "ticket": result.data}


@app.put("/metadata", tags=["Write Operations"])
async def update_metadata(
    request: UpdateMetadataRequest,
    supervisor: SupervisorAgent = Depends(get_supervisor),
):
    """Update a governance metadata attribute in Collibra."""
    from core.base_agent import AgentRequest
    agent_request = AgentRequest(
        query=f"update {request.attribute} for {request.asset_name} to {request.value}",
        context={
            "asset_name": request.asset_name,
            "attribute": request.attribute,
            "value": request.value,
        },
    )
    metadata_agent = supervisor.agents["metadata"]
    result = metadata_agent.execute(agent_request)
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    return {"status": "success", "result": result.data}


@app.post("/rules", tags=["Write Operations"])
async def create_rule(
    request: CreateRuleRequest,
    supervisor: SupervisorAgent = Depends(get_supervisor),
):
    """Create a new business or data quality rule."""
    from core.base_agent import AgentRequest
    agent_request = AgentRequest(
        query=f"create rule {request.rule_name}",
        context={
            "rule_name": request.rule_name,
            "dimension": request.dimension,
            "asset": request.asset,
            "expression": request.expression,
            "threshold": request.threshold,
            "severity": request.severity,
        },
        data_products=[request.asset],
    )
    rule_agent = supervisor.agents["rule"]
    result = rule_agent.execute(agent_request)
    return {"status": "success", "rule": result.data}


@app.get("/data-products", tags=["Reference"])
async def list_data_products():
    """List all registered data products."""
    from config.settings import DATA_PRODUCTS
    return {"data_products": DATA_PRODUCTS}


# ---------------------------------------------------------------------------
# Adaptive Card builder for Teams
# ---------------------------------------------------------------------------

def _build_adaptive_card(response) -> Dict:
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "🏛️ Data Governance Copilot", "weight": "Bolder", "color": "Accent"},
            {"type": "TextBlock", "text": response.final_summary[:800], "wrap": True},
            {
                "type": "FactSet",
                "facts": [
                    {"title": "Intent", "value": response.intent},
                    {"title": "Confidence", "value": f"{response.overall_confidence:.0%}"},
                    {"title": "Data Products", "value": ", ".join(response.data_products_referenced)},
                ],
            },
        ],
        "actions": [
            {"type": "Action.Submit", "title": "Create Jira Ticket", "data": {"action": "create_ticket"}},
            {"type": "Action.OpenUrl", "title": "View in Dashboard", "url": "https://your-dashboard-url"},
        ],
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=config.debug, log_level="info")
