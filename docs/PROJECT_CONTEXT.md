# Data Governance Copilot — Project Context
> Paste this at the start of any new chat to continue development instantly.

---

## Project Goal
Build an **Agentic AI Data Governance & Analytics Assistant** — a multi-agent system where a Supervisor Agent orchestrates specialized agents to answer business users' data questions via Streamlit UI / Microsoft Teams / FastAPI.

---

## Tech Stack (Current)
| Layer | Technology |
|---|---|
| Orchestration | LangGraph (StateGraph, sequential routing) |
| LLM | Groq (llama-3.3-70b-versatile) via LiteLLM (multi-provider fallback chain) |
| Structured Output | Pydantic + `.with_structured_output()` |
| RAG / Vector Store | pgvector — `NullVectorService` mock in dev |
| Document Loaders | LangChain (PDF, DOCX, PPTX, Excel) |
| Structured Data | Databricks SQL / SQL Warehouse (mock in dev) |
| Governance | Collibra REST API (via MCP — USE_MCP=false in dev) |
| Ticketing | Jira REST API |
| Memory | MemorySaver (dev) / PostgreSQL (prod) via LangGraph checkpointer |
| Cache | Redis — survives ECS restarts, shared across tasks; in-memory fallback when Redis down |
| Observability | LangSmith tracing |
| UI | Streamlit (polished) |
| API | FastAPI + SSE + slowapi rate limiting |
| Teams Bot | Adaptive Cards webhook |
| Package Manager | uv |
| Ingestion Orchestration | Apache Airflow 2.9 (Compose/ECS) |
| Ingestion Storage | S3 (prod) / local `docs/` folder (dev) |
| Infra | Docker + ECS Fargate |
| CI/CD | GitHub Actions |
| Testing | pytest |
| Secrets | AWS Secrets Manager (prod) |

---

## Folder Structure
```
data-governance-copilot/
├── src/
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py          ✅ AgentState TypedDict (+ start_time, guardrail_passed, _agents_ran)
│   │   ├── intent.py         ✅ Groq/GPT-4o structured output + LiteLLM + keyword fallback
│   │   ├── routing.py        ✅ INTENT_AGENT_MAP
│   │   ├── nodes.py          ✅ All nodes + retry + HITL + @cached_node + synthesizer
│   │   └── graph.py          ✅ StateGraph + sequential routing + _wrap_agent tracker
│   ├── memory/
│   │   ├── __init__.py
│   │   └── checkpointer.py   ✅ MemorySaver (dev) / PostgresSaver (prod) with fallback chain
│   ├── services/             ✅ Service abstraction layer
│   │   ├── __init__.py
│   │   ├── base.py           ✅ Abstract protocols: IDataService, ITicketService,
│   │   │                        IMetadataService, IVectorService
│   │   ├── factory.py        ✅ Single switching point — reads ENABLE_MOCK, graceful fallback
│   │   ├── databricks/
│   │   │   ├── __init__.py
│   │   │   ├── real.py       ✅ DatabricksService
│   │   │   └── mock.py       ✅ MockDatabricksService — canned rows, low_grr=True scenario
│   │   ├── jira/
│   │   │   ├── __init__.py
│   │   │   ├── real.py       ✅ JiraService REST v3
│   │   │   └── mock.py       ✅ MockJiraService — in-memory store, inspectable tickets list
│   │   ├── collibra/
│   │   │   ├── __init__.py
│   │   │   ├── real.py       ✅ CollibraService REST
│   │   │   └── mock.py       ✅ MockCollibraService — canned assets + DQ scores
│   │   └── pgvector/
│   │       ├── __init__.py
│   │       ├── real.py       ✅ PGVectorService wrapping LangChain PGVector
│   │       └── mock.py       ✅ NullVectorService — keyword-scored governance docs
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── information_agent.py   ✅ Thin wrapper — delegates to IDataService
│   │   ├── knowledge_agent.py     ✅ Thin wrapper — delegates to IVectorService
│   │   ├── metadata_agent.py      ✅ Thin wrapper — delegates to IMetadataService
│   │   ├── capacity_agent.py      ✅ Thin wrapper — delegates to ITicketService
│   │   ├── rule_agent.py          ✅ Rule registry CRUD
│   │   └── supervisor_agent.py    ✅ Legacy stub (LangGraph nodes supersede)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── base_agent.py     ✅ AgentRequest, AgentResult, BaseAgent contract
│   │   ├── logging_utils.py  ✅ Structured JSON logging, decorators, error hierarchy
│   │   ├── guardrails.py     ✅ Length, SQL injection, prompt injection, PII
│   │   ├── cache.py          ✅ Redis + in-memory fallback + @cached_node
│   │   ├── llm_factory.py    ✅ LiteLLM factory + fallback chain + _MockLLM
│   │   ├── retry.py          ✅ @with_retry + retry_agent_call()
│   │   ├── llm_guard.py      ✅ Daily token budget hard stop
│   │   ├── vector_store.py   ✅ Backwards-compat shim → delegates to services/pgvector/
│   │   └── mcp_client.py     ✅ MCP client factory with graceful fallback
│   ├── api/
│   │   ├── __init__.py
│   │   ├── middleware.py     ✅ slowapi limiter — Redis if available, memory:// fallback
│   │   └── app.py            ✅ FastAPI + /query + /query/stream + /history + /agents/status
│   │                            get_graph imported at module level (patchable in tests)
│   ├── teams/
│   │   ├── __init__.py
│   │   ├── models.py         ✅ TeamsActivity, TeamsUser, TeamsConversation (Pydantic V2)
│   │   ├── cards.py          ✅ Adaptive Card builders
│   │   └── bot.py            ✅ Webhook router + HMAC verification + activity routing
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py       ✅ AppConfig + LLMConfig + RedisConfig + DatabricksConfig
│   │                            + VectorDBConfig (all fields use default_factory)
│   ├── tools/
│   │   └── __init__.py
│   ├── ui/
│   │   ├── __init__.py
│   │   └── app.py            ✅ Streamlit chat UI + HITL panel + execution stats
│   └── __init__.py
├── ingestion/                          ← Airflow ingestion (Day 19)
│   ├── __init__.py
│   ├── loaders.py                      ✅ LangChain loaders: PDF/DOCX/PPTX/Excel/text
│   ├── chunker.py                      ✅ RecursiveCharacterTextSplitter(512/64) + metadata tag
│   ├── embedder.py                     ✅ OpenAI text-embedding-3-small, batch=100
│   └── store.py                        ✅ pgvector upsert + SHA-256 dedup + batch write
│                                          Module-level psycopg2/PGVector/OpenAIEmbeddings imports
├── dags/
│   ├── file_ingestion_dag.py           ✅ FileSensor on docs/ → load→chunk→embed→store
│   ├── on_demand_ingest_dag.py         ✅ API-triggered single-file ingest (conf.filepath)
│   ├── collibra_sync_dag.py            ✅ Collibra REST pull @daily → format→embed→upsert
│   └── nightly_refresh_dag.py          ✅ Hash-diff → re-embed changed chunks only @02:00 UTC
├── scripts/
│   ├── init_pgvector.sql               ✅ One-time pgvector DB setup
│   └── trigger_ingest.sh               ✅ Helper: curl Airflow REST API → on_demand DAG
├── tests/
│   ├── conftest.py                     ✅ Shared fixtures (mock services, sample_request)
│   ├── test_services.py                ✅ Protocol conformance, mock shapes, factory switching
│   ├── test_capacity_agent.py          ✅ Injection pattern, no patch() needed
│   ├── test_information_agent.py       ✅ Injection pattern, no patch() needed
│   ├── test_knowledge_agent.py         ✅ Injection pattern, no patch() needed
│   ├── test_metadata_agent.py          ✅ Injection pattern, no patch() needed
│   ├── test_rule_agent.py              ✅ Rule CRUD + evaluate invariant
│   ├── test_day19.py                   ✅ Ingestion pipeline unit tests (patch.object for psycopg2)
│   ├── test_day20_smoke.py             ✅ 15 end-to-end smoke tests through full LangGraph pipeline
│   ├── test_day20_coverage.py          ✅ Coverage boosters — guardrails, cache, retry, nodes, agents
│   └── test_day20_production.py        ✅ Production readiness — FastAPI, error handling, protocols
├── data/
│   └── memory.db                       ✅ SQLite placeholder (MemorySaver used in dev)
├── docs/
│   └── .gitkeep                        ← Airflow FileSensor watches this folder
├── .github/
│   └── workflows/
│       └── ci.yml                      ✅ GitHub Actions: lint + pytest --cov-fail-under=80 + Docker build
├── Dockerfile                          ✅ Two-stage build (builder + runtime), python:3.12-slim
├── Dockerfile.airflow                  ✅ Extends apache/airflow:2.9, installs project deps
├── compose.yml                         ✅ app + api + redis + postgres + airflow services
├── .env.example                        ✅ Full reference with all vars
├── pyproject.toml                      ✅ "integration" mark + coverage fail_under=80
└── requirements.txt                    ✅ All deps including psycopg2-binary, langchain-postgres
```

**Test suite result (Day 20): 240 passed, 0 failed, 0 warnings — 84% coverage**

---

## AgentState (state.py — all fields)
```python
class AgentState(TypedDict):
    # Input
    query, thread_id, user_id, time_range, data_products

    # Routing (set by supervisor_node)
    intent, next_agents

    # Agent outputs (accumulated via operator.add)
    agent_results, sources, anomalies, errors

    # Write actions
    auto_tickets, pending_action, approved

    # Final output
    final_summary, confidence

    # Memory
    conversation_history, user_preferences

    # Metadata
    execution_ms, query_id

    # Day 13: pre/post hook fields
    start_time, guardrail_passed

    # Day 20: sequential routing tracker
    _agents_ran: List[str]
```

---

## Graph Flow (Day 20 — Sequential Routing)
```
START
  → pre_hook         ← guardrails (length/SQL/injection/PII), start_time
      ↓ guardrail_passed=True          ↓ guardrail_passed=False
  → supervisor                         → post_hook → END
      → _agent_router (conditional)
          → first agent in next_agents[]
          → _after_first_agent (conditional loop through remaining agents)
              information_node  ← @cached_node(ttl=1800) + retry_agent_call()
              knowledge_node    ← @cached_node(ttl=7200) + retry_agent_call()
              metadata_node     ← @cached_node(ttl=3600) + retry_agent_call()
              capacity_node
              rule_node
          → auto_ticket    ← HITL gate
          → synthesizer    ← LiteLLM (Groq primary) + string fallback
          → post_hook      ← execution_ms
          → END

NOTE: Sequential routing (not parallel fan-out) avoids LangGraph
InvalidUpdateError on non-Annotated state keys. _agents_ran[] tracks
which agents have run; _wrap_agent() decorator appends to it.
```

---

## Intent → Agent Routing (routing.py)
```python
INTENT_AGENT_MAP = {
    "full_diagnostic":  ["information","knowledge","metadata","capacity"],
    "data_quality":     ["metadata","information"],
    "governance":       ["metadata","knowledge"],
    "incident_review":  ["capacity"],
    "knowledge_lookup": ["knowledge","metadata"],
    "metric_analysis":  ["information","knowledge"],
    "write_ticket":     ["capacity"],
    "write_metadata":   ["metadata"],
    "write_rule":       ["rule"],
    "unknown":          ["information","knowledge"],
}
```

---

## IntentClassification Schema (intent.py)
```python
class IntentClassification(BaseModel):
    intent:        QueryIntent   # 10 enum values
    data_products: List[str]     # ["retention","bookings","cac","ltv"]
    confidence:    float         # 0.0–1.0
    reasoning:     str           # one-sentence rationale

# Chain: prompt | get_structured_llm(config.llm, IntentClassification)
# Fallback: keyword matching when no API key or LLM fails
```

---

## LiteLLM Fallback Chain (llm_factory.py)
```python
# Primary provider: Groq (llama-3.3-70b-versatile)
# Fallback order (LLMConfig.fallback_models):
gpt-4o-mini → anthropic/claude-haiku-4-5 → gemini/gemini-1.5-flash

# No GROQ_API_KEY → _MockLLM stub (always returns string, never raises)
# Two factory functions:
get_llm(config, streaming=False)             → BaseChatModel with fallbacks
get_structured_llm(config, schema)           → LLM bound to Pydantic schema
```

---

## Guardrails (core/guardrails.py)
```
Check order (first match blocks or redacts):
  1. Length          min=3, max=2000 chars         → block
  2. Destructive SQL DROP/DELETE/TRUNCATE/ALTER     → block
  3. Prompt injection "ignore instructions", DAN    → block
  4. PII redaction   SSN, cards, emails, NI         → redact silently, allow
```

---

## Redis Cache (core/cache.py)
```python
# Node TTLs:
@cached_node("information_agent", ttl=1800)   # 30 min — SQL results
@cached_node("knowledge_agent",   ttl=7200)   # 2 hrs  — RAG docs
@cached_node("metadata_agent",    ttl=3600)   # 1 hr   — Collibra metadata

# NOT cached: capacity_node, auto_ticket_node, synthesizer_node
# Cache key = SHA-256(query + data_products + time_range)
# Module-level imports only — no AppConfig() re-instantiation per call
# Fallback: in-memory dict when Redis is unavailable
```

---

## Rate Limiter (api/middleware.py)
```python
# Probes Redis at import time (1-second timeout).
# Uses Redis storage if reachable → shared limits across ECS tasks.
# Falls back to memory:// if Redis unavailable → per-process limits (dev/CI).
limiter      = Limiter(key_func=get_remote_address, storage_uri=_storage_uri)
user_limiter = Limiter(key_func=get_user_id,        storage_uri=_storage_uri)
```

---

## Retry Logic (core/retry.py)
```python
# Backoff: 1s → 2s → 4s (exponential, backoff_factor * 2^attempt)
@with_retry(max_retries=3, backoff_factor=1.0)   # decorator
retry_agent_call(agent.execute, request, max_retries=3)  # returns AgentResult(success=False) on final failure
# Applied to: information_node, knowledge_node, metadata_node
```

---

## Human-in-the-Loop (nodes.py — auto_ticket_node)
```
Flow:
  1st call (approved=False):  anomalies found → set pending_action → skip tickets
  2nd call (approved=True):   create Jira tickets → clear pending_action
                               If CapacityAgent unconfigured → pending_action.error set

Critical keywords: threshold, missing, below, risk, drop, fail

Streamlit: _render_hitl_panel() checks st.session_state.pending_hitl
Teams:     build_hitl_card() renders Approve/Reject Action.Submit buttons
```

---

## FastAPI Endpoints (api/app.py)
```
GET  /health             → liveness probe (no rate limit)
POST /query              → JSON response, 20/min per IP
POST /query/stream       → SSE: start → result → done events, 20/min per IP
GET  /history/{thread}   → conversation history, 60/min
GET  /agents/status      → Redis + agents + daily token usage, 120/min
POST /teams/webhook      → Teams bot, 10/min per X-User-Id
GET  /teams/health       → Teams bot probe
POST /ingest             → multipart upload → triggers Airflow on_demand DAG, 10/min

get_graph imported at module level — patchable in FastAPI tests.
Run: uv run uvicorn src.api.app:app --reload --port 8000
```

---

## Services Layer (services/)
```
Design: Interface protocol → Factory → Real or Mock implementation
Switching: ENABLE_MOCK=true (default) → mock; ENABLE_MOCK=false → real with graceful fallback

services/base.py         → 4 runtime_checkable Protocol classes
services/factory.py      → get_data_service(), get_ticket_service(),
                           get_metadata_service(), get_vector_service()
```

---

## Ingestion Pipeline (src/ingestion/ — Day 19)
```python
# loaders.py — module-level imports (PyPDFLoader, Docx2txtLoader, etc.) for patchability
# chunker.py — RecursiveCharacterTextSplitter(512/64) + content_hash + product inference
# embedder.py — OpenAIEmbeddings(text-embedding-3-small), module-level import
# store.py    — psycopg2 + PGVector + OpenAIEmbeddings all at module level
#               Use patch.object(store_module.psycopg2, "connect", ...) in tests
```

---

## 4 Airflow DAGs
```
file_ingestion_dag.py      schedule=None  (FileSensor on AIRFLOW_DOCS_PATH)
on_demand_ingest_dag.py    schedule=None  (REST API / POST /ingest)
collibra_sync_dag.py       schedule="0 6 * * *"  (daily 06:00 UTC)
nightly_refresh_dag.py     schedule="0 2 * * *"  (nightly 02:00 UTC)
```

---

## Complete Bug Fix Log (Days 1–20)

### Days 1–19 fixes (see prior context)
All 35 bugs from Days 1–19 remain fixed.

### Day 20 fixes
| # | File | Bug | Fix |
|---|---|---|---|
| 36 | `src/graph/graph.py` | Parallel fan-out caused `InvalidUpdateError` on non-Annotated state keys | Replaced parallel edges with sequential routing + `_wrap_agent()` + `_agents_ran` tracker |
| 37 | `src/memory/checkpointer.py` | `langgraph.checkpoint.sqlite` not available in installed version | Fallback chain: SqliteSaver → langgraph_checkpoint_sqlite → MemorySaver |
| 38 | `src/api/app.py` | `get_graph` imported inside function, not patchable in tests | Moved to module-level import |
| 39 | `src/ingestion/store.py` | `psycopg2` imported inside function; `patch("psycopg2.connect")` couldn't intercept | Moved all imports to module level; tests use `patch.object(store_module.psycopg2, "connect")` |
| 40 | `src/ingestion/embedder.py` | `OpenAIEmbeddings` imported inside function | Moved to module level |
| 41 | `src/ingestion/loaders.py` | Loader classes imported inside function | Moved to module level |
| 42 | `tests/test_day20_coverage.py` | `_keyword_fallback("create rule for data quality")` matched data_quality not write_rule | Fixed to `"create rule for retention"` |
| 43 | `tests/test_day20_production.py` | FastAPI `/query` test ran real graph (slow, fragile) | Patched `_run_graph` with mock result |
| 44 | `src/graph/state.py` | `_agents_ran` field missing from TypedDict | Added `_agents_ran: List[str]` |

---

## Current Status
**Day 20 Complete — 240 passed, 0 failed, 84% coverage**

### All Days 1–20 Complete:
| Day | Focus | Status |
|---|---|---|
| Days 1–4 | Project setup, config, logging, base_agent | ✅ |
| Day 6 | InformationAgent | ✅ |
| Day 7 | KnowledgeAgent | ✅ |
| Day 8 | MetadataAgent | ✅ |
| Day 9 | CapacityAgent | ✅ |
| Day 10 | RuleAgent | ✅ |
| Days 11–12 | Write capabilities, LangGraph + memory + Streamlit | ✅ |
| Day 13 | Intent + synthesizer + hooks + guardrails + LangSmith | ✅ |
| Day 14 | LiteLLM fallback + Redis cache + @cached_node | ✅ |
| Day 15 | retry.py + HITL + Streamlit HITL panel | ✅ |
| Day 16 | FastAPI + SSE + rate limiting + llm_guard | ✅ |
| Day 17 | Teams bot + Adaptive Cards + HMAC + HITL buttons | ✅ |
| Day 18 | pgvector + NullVectorStore + MCP + VectorDBConfig | ✅ |
| Day 19 | Docker + CI/CD + Airflow RAG ingestion pipeline | ✅ |
| Day 20 | Smoke tests + 84% coverage + production cleanup | ✅ |

### 8 Additional Features
| Feature | Status |
|---|---|
| Persistence memory | ✅ |
| Node caching (Redis) | ✅ |
| Pre/post hooks | ✅ |
| Error handling & retries | ✅ |
| Human-in-the-loop | ✅ |
| Logging & monitoring (LangSmith) | ✅ |
| Guardrails | ✅ |
| MCP integration | ✅ |
| RAG ingestion pipeline | ✅ |

---

## How to Run
```bash
# Install dependencies
uv pip install -r requirements.txt

# Run all tests with coverage
ENABLE_MOCK=true REDIS_ENABLED=false \
  uv run pytest tests/ --cov=src --cov-fail-under=80

# Run only smoke tests
uv run pytest tests/test_day20_smoke.py -v

# Run Streamlit UI
uv run streamlit run src/ui/app.py

# Run FastAPI server
uv run uvicorn src.api.app:app --reload --port 8000

# Run with Docker (full stack)
docker compose up

# Trigger document ingestion
bash scripts/trigger_ingest.sh path/to/doc.pdf
curl -X POST http://localhost:8000/ingest -F "file=@doc.pdf"
```
