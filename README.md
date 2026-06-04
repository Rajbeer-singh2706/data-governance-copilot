# 🏛️ Data Governance Copilot



## updated
## uv python install 3.11
## uv venv --python 3.11
## uv init --name data_gov_env
## uv add -r requriments.txt


### TO RUN Streamlit ########
## uv run streamlit run src/ui/app.py 

### to run fastAPI Server ######
# uvicorn src.api.app:app --host 0.0.0.0 --port 8000

http://localhost:8000/docs#

##### RUN ####

A production-ready, modular **multi-agent AI system** that acts as a conversational interface for business users to interact with enterprise data products (Bookings, Retention, LTV, CAC). Built on a Supervisor + Specialist agent pattern with full Read/Write capabilities.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER INTERFACE                               │
│            Streamlit Web UI  ◄──►  Teams Bot (FastAPI)              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ Natural Language Query
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SUPERVISOR AGENT (Orchestrator)                  │
│  1. Intent Classification  →  2. Agent Selection                   │
│  3. Parallel Execution     →  4. Response Aggregation              │
│  5. LLM Synthesis (GPT-4o) →  6. Auto-Action Triggering           │
└───────┬──────────┬──────────┬──────────┬──────────┬────────────────┘
        │          │          │          │          │
        ▼          ▼          ▼          ▼          ▼
  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
  │Knowledge │ │  Info    │ │Metadata  │ │Capacity  │ │  Rule    │
  │  Agent   │ │  Agent   │ │  Agent   │ │  Agent   │ │  Agent   │
  │          │ │          │ │          │ │          │ │          │
  │ RAG/FAISS│ │Databricks│ │Collibra  │ │  Jira    │ │Rule Reg. │
  │SharePoint│ │SQL DWH   │ │  MCP     │ │  API     │ │          │
  │Confluence│ │          │ │          │ │          │ │          │
  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
     READ          READ      READ/WRITE   READ/WRITE     WRITE
```

---

## Agent Responsibilities

| Agent | Mode | Integrations | Capabilities |
|---|---|---|---|
| **Supervisor** | Orchestrate | All agents | Intent parsing, routing, LLM synthesis |
| **Knowledge** | Read | SharePoint, Confluence, FAISS/Chroma | Business definitions, runbooks, RAG |
| **Information** | Read | Databricks, SQL DWH | Metrics, trends, anomaly detection |
| **Metadata** | Read + Write | Collibra DGC (MCP) | DQ scores, ownership, lineage, classifications |
| **Capacity** | Read + Write | Jira REST API | Issues, incidents, ticket creation |
| **Rule** | Write | Internal registry | DQ rules, business rules, evaluation |

---

## Intent Routing

| User Query | Intent | Agents Triggered |
|---|---|---|
| *"Why did retention drop?"* | `full_diagnostic` | All 4 read agents |
| *"What is the DQ score for CAC?"* | `data_quality` | Metadata + Information |
| *"Who owns the bookings dataset?"* | `governance` | Metadata + Knowledge |
| *"Open Jira bugs for retention"* | `incident_review` | Capacity |
| *"What is GRR?"* | `knowledge_lookup` | Knowledge + Metadata |
| *"Create a bug ticket"* | `write_ticket` | Capacity (write) |
| *"Update metadata owner"* | `write_metadata` | Metadata (write) |
| *"Create a DQ rule"* | `write_rule` | Rule (write) |

---

## Project Structure

```
data-governance-copilot/
├── agents/
│   ├── supervisor_agent.py    # Orchestrator — intent routing, parallel execution, LLM synthesis
│   ├── information_agent.py   # Databricks/SQL metrics, anomaly detection
│   ├── knowledge_agent.py     # RAG over PDFs/DOCX/PPTX, SharePoint, Confluence
│   ├── metadata_agent.py      # Collibra DGC — DQ scores, ownership, lineage
│   ├── capacity_agent.py      # Jira — read issues, create tickets
│   └── rule_agent.py          # Business rules and DQ rule management
├── core/
│   ├── base_agent.py          # BaseAgent, AgentRequest, AgentResult abstractions
│   └── logging_utils.py       # JSON structured logging, retry decorator, error types
├── config/
│   └── settings.py            # Centralised config (LLM, Databricks, Collibra, Jira, etc.)
├── ui/
│   ├── app.py                 # Streamlit Web UI
│   └── api.py                 # FastAPI REST + Teams Bot webhook
├── tests/
│   └── test_agents.py         # Pytest unit tests for all agents
├── demo.py                    # CLI demo — runs 7 sample queries end-to-end
├── requirements.txt
├── .env.example
├── Dockerfile
└── docker-compose.yml
```

---

## Quick Start

### 1. Clone & install

```bash
git clone <repo-url>
cd data-governance-copilot
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set ENABLE_MOCK=true to start without real credentials
```

### 3. Run the CLI demo (no credentials required)

```bash
python demo.py
```

### 4. Launch the Streamlit Web UI

```bash
streamlit run ui/app.py
# Open http://localhost:8501
```

### 5. Start the REST API

```bash
python ui/api.py
# API docs at http://localhost:8000/docs
```

### 6. Docker Compose (full stack)

```bash
docker-compose up --build
# Web UI:  http://localhost:8501
# API:     http://localhost:8000
# Chroma:  http://localhost:8002
```

### 7. Run tests

```bash
pytest tests/ -v
```

---

## API Reference

### POST /query
Main query endpoint. Accepts natural language and returns unified analysis.

```json
POST /query
{
  "query": "Why did retention drop last month?",
  "time_range": "last_month",
  "data_products": ["retention"],
  "user_id": "john.doe@company.com",
  "source": "api"
}
```

### POST /tickets
Create a Jira ticket directly.

```json
POST /tickets
{
  "summary": "EU retention data missing for 3 days",
  "description": "Pipeline failure in Databricks job retention_etl_eu",
  "issue_type": "Bug",
  "priority": "High",
  "data_product": "retention",
  "labels": ["data-quality", "etl-failure"]
}
```

### PUT /metadata
Update a governance attribute in Collibra.

```json
PUT /metadata
{
  "asset_name": "Gross Retention Rate",
  "attribute": "owner",
  "value": "jane.smith@company.com",
  "justification": "Ownership transferred after org restructure"
}
```

### POST /rules
Create a new DQ or business rule.

```json
POST /rules
{
  "rule_name": "Retention Completeness Check",
  "rule_type": "data_quality",
  "asset": "analytics.retention_metrics",
  "expression": "null_count / total_count < 0.01",
  "dimension": "completeness",
  "threshold": 0.01,
  "severity": "High"
}
```

### GET /health
Returns health status of all agents and integrations.

---

## Adding a New Agent

1. Create `agents/my_agent.py` inheriting from `BaseAgent`
2. Implement `_execute(self, request: AgentRequest) -> AgentResult`
3. Register in `SupervisorAgent.__init__()`: `self.agents["my_agent"] = MyAgent(...)`
4. Add routing rules in `INTENT_AGENT_MAP` in `supervisor_agent.py`
5. Add tests in `tests/test_agents.py`

```python
from core.base_agent import BaseAgent, AgentRequest, AgentResult

class MyAgent(BaseAgent):
    name = "my_agent"
    description = "Does something specific"
    capabilities = ["capability_a", "capability_b"]

    def _execute(self, request: AgentRequest) -> AgentResult:
        # Your domain logic here
        return AgentResult(
            agent_name=self.name,
            success=True,
            summary="Result summary",
            data={"key": "value"},
            sources=["My Data Source"],
        )
```

---

## Production Considerations

- **LLM**: Switch `LLM_PROVIDER` to `azure_openai` and set Azure credentials
- **Mock → Real**: Set `ENABLE_MOCK=false` and provide real connector credentials
- **Scaling**: Each agent is stateless — deploy behind a load balancer
- **Auth**: Add JWT/OAuth middleware to `api.py` for production API security
- **Observability**: JSON structured logs ship to any log aggregator (Datadog, Splunk, ELK)
- **Vector Store**: FAISS for single-node; Chroma with persistence for multi-replica
- **Knowledge Ingestion**: Call `KnowledgeAgent.ingest_document(path)` to index new PDFs/DOCX

---

## Tech Stack

| Layer | Technology |
|---|---|
| Orchestration | LangGraph / Custom Supervisor |
| LLM | OpenAI GPT-4o / Azure OpenAI |
| RAG / Embeddings | FAISS + OpenAI text-embedding-3-small |
| Data Source | Databricks SQL Connector |
| Governance | Collibra DGC REST API |
| Ticketing | Jira REST API v3 |
| Document Parsing | LangChain + Unstructured |
| REST API | FastAPI + Uvicorn |
| Web UI | Streamlit |
| Containers | Docker + Docker Compose |
| Testing | Pytest |
| Logging | Python logging (JSON structured) |
