# Data Governance Copilot — Project Context
> Paste this at the start of any new chat to continue development instantly.

---

## Project Goal
Build an **Agentic AI Data Governance & Analytics Assistant** — a multi-agent system where a Supervisor Agent orchestrates specialized agents to answer business users' data questions via Streamlit UI / Microsoft Teams / FastAPI.

---

## Tech Stack (Current)
| Layer | Technology |
|---|---|
| Orchestration | LangGraph (StateGraph) |
| LLM | Groq (llama-3.3-70b-versatile) via LiteLLM (multi-provider fallback chain) |
| Structured Output | Pydantic + `.with_structured_output()` |
| RAG / Vector Store | pgvector — `NullVectorService` mock in dev |
| Document Loaders | LangChain (PDF, DOCX, PPTX, Excel) |
| Structured Data | Databricks SQL / SQL Warehouse (mock in dev) |
| Governance | Collibra REST API (via MCP — USE_MCP=false in dev) |
| Ticketing | Jira REST API |
| Memory | SQLite (dev) / PostgreSQL (prod) via LangGraph checkpointer |
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
│   │   ├── state.py          ✅ AgentState TypedDict (+ start_time, guardrail_passed)
│   │   ├── intent.py         ✅ Groq/GPT-4o structured output + LiteLLM + keyword fallback
│   │   ├── routing.py        ✅ INTENT_AGENT_MAP
│   │   ├── nodes.py          ✅ All nodes + retry + HITL + @cached_node + synthesizer
│   │   │                        auto_ticket_node guards create_ticket_from_anomaly
│   │   │                        with hasattr() to avoid _UnconfiguredAgent crash
│   │   └── graph.py          ✅ StateGraph + pre/post hooks + guardrail conditional edge
│   ├── memory/
│   │   ├── __init__.py
│   │   └── checkpointer.py   ✅ SqliteSaver (dev) / PostgresSaver (prod)
│   ├── services/             ✅ Service abstraction layer
│   │   ├── __init__.py
│   │   ├── base.py           ✅ Abstract protocols: IDataService, ITicketService,
│   │   │                        IMetadataService, IVectorService
│   │   ├── factory.py        ✅ Single switching point — reads ENABLE_MOCK, graceful fallback
│   │   ├── databricks/
│   │   │   ├── __init__.py
│   │   │   ├── real.py       ✅ DatabricksService (moved from information_agent)
│   │   │   └── mock.py       ✅ MockDatabricksService — canned rows, low_grr=True scenario
│   │   ├── jira/
│   │   │   ├── __init__.py
│   │   │   ├── real.py       ✅ JiraService REST v3 (moved from capacity_agent)
│   │   │   └── mock.py       ✅ MockJiraService — in-memory store, inspectable tickets list
│   │   ├── collibra/
│   │   │   ├── __init__.py
│   │   │   ├── real.py       ✅ CollibraService REST (moved from metadata_agent)
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
│   │   │                             create_ticket_from_anomaly() public method retained
│   │   ├── rule_agent.py          ✅ Rule registry CRUD (unchanged)
│   │   └── supervisor_agent.py    ✅ Orchestrator (legacy — tests skip gracefully)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── base_agent.py     ✅ AgentRequest, AgentResult, BaseAgent contract
│   │   ├── logging_utils.py  ✅ Structured JSON logging, decorators, error hierarchy
│   │   ├── guardrails.py     ✅ Length, SQL injection, prompt injection, PII
│   │   ├── cache.py          ✅ Redis + in-memory fallback + @cached_node
│   │   ├── llm_factory.py    ✅ LiteLLM factory + fallback chain
│   │   ├── retry.py          ✅ @with_retry + retry_agent_call()
│   │   ├── llm_guard.py      ✅ Daily token budget hard stop
│   │   ├── vector_store.py   ✅ Backwards-compat shim → delegates to services/pgvector/
│   │   └── mcp_client.py     ✅ MCP client factory with graceful fallback
│   ├── api/
│   │   ├── __init__.py
│   │   ├── middleware.py     ✅ slowapi limiter — Redis if available, memory:// fallback
│   │   └── app.py            ✅ FastAPI + /query + /query/stream + /history + /agents/status
│   ├── teams/
│   │   ├── __init__.py
│   │   ├── models.py         ✅ TeamsActivity, TeamsUser, TeamsConversation (Pydantic V2)
│   │   ├── cards.py          ✅ Adaptive Card builders
│   │   └── bot.py            ✅ Webhook router + HMAC verification + activity routing
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py       ✅ AppConfig + LLMConfig + RedisConfig + DatabricksConfig
│   │                             + VectorDBConfig (all fields use default_factory)
│   ├── tools/
│   │   └── __init__.py
│   ├── ui/
│   │   ├── __init__.py
│   │   └── app.py            ✅ Streamlit chat UI + HITL panel + execution stats
│   └── __init__.py
├── ingestion/                          ← Airflow ingestion (Day 19)
│   ├── __init__.py
│   ├── loaders.py                      ✅ LangChain loaders: PDF/DOCX/PPTX/Excel/text/web
│   ├── chunker.py                      ✅ RecursiveCharacterTextSplitter(512/64) + metadata tag
│   ├── embedder.py                     ✅ OpenAI text-embedding-3-small, batch=100
│   └── store.py                        ✅ pgvector upsert + SHA-256 dedup + batch write
├── dags/                               ← Airflow DAGs (Day 19)
│   ├── file_ingestion_dag.py           ✅ FileSensor on docs/ → load→chunk→embed→store
│   ├── on_demand_ingest_dag.py         ✅ API-triggered single-file ingest (conf.filepath)
│   ├── collibra_sync_dag.py            ✅ Collibra REST pull @daily → format→embed→upsert
│   └── nightly_refresh_dag.py          ✅ Hash-diff → re-embed changed chunks only @02:00 UTC
├── scripts/
│   ├── init_pgvector.sql               ✅ One-time pgvector DB setup
│   └── trigger_ingest.sh               ✅ Helper: curl Airflow REST API → on_demand DAG
├── tests/
│   ├── test_services.py                ✅ 33 tests: protocol conformance, mock shapes,
│   │                                      factory switching, agent injection
│   ├── test_capacity_agent.py          ✅ Rewritten — injection pattern, no patch() needed
│   ├── test_information_agent.py       ✅ Rewritten — injection pattern, no patch() needed
│   ├── test_knowledge_agent.py         ✅ Rewritten — injection pattern, no patch() needed
│   ├── test_metadata_agent.py          ✅ Rewritten — injection pattern, no patch() needed
│   ├── test_day1.py                    ✅
│   ├── test_day14.py                   ✅
│   ├── test_day15.py                   ✅
│   ├── test_day16.py                   ✅
│   ├── test_day17.py                   ✅
│   ├── test_day18.py                   ✅ NullVectorService import from services/pgvector/mock
│   ├── test_day19.py                   ✅ ingestion pipeline unit tests
│   └── test_rule_agent.py              ✅
├── data/
│   └── memory.db                       ✅ SQLite conversation memory
├── docs/
│   └── (governance PDFs / DOCX drop-zone) ← Airflow FileSensor watches this folder
├── .github/
│   └── workflows/
│       └── ci.yml                      ✅ GitHub Actions: lint + pytest + Docker build
├── Dockerfile                          ✅ Two-stage build (builder + runtime), python:3.12-slim
├── Dockerfile.airflow                  ✅ Extends apache/airflow:2.9, installs project deps
├── compose.yml                         ✅ app + api + redis + postgres + airflow services
├── .env                                ✅ All vars (see reference below)
├── .env.example                        ✅ Full reference with all vars
├── .gitignore
├── pyproject.toml                      ✅ "integration" mark registered
└── requirements.txt                    ✅ Cleaned — no chromadb/faiss-cpu
```

**Test suite result (after services refactor + Day 19): 195 passed, 4 skipped, 0 failed, 0 warnings**
The 4 skipped are supervisor_agent tests referencing a legacy path — they skip gracefully via `pytest.skip()`.

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
```

---

## Graph Flow
```
START
  → pre_hook         ← guardrails (length/SQL/injection/PII), start_time
      ↓ guardrail_passed=True          ↓ guardrail_passed=False
  → supervisor                         → post_hook → END
      → [parallel agents via Send()]
          information_node  ← @cached_node(ttl=1800) + retry_agent_call()
          knowledge_node    ← @cached_node(ttl=7200) + retry_agent_call()
          metadata_node     ← @cached_node(ttl=3600) + retry_agent_call()
          capacity_node
          rule_node
      → auto_ticket    ← HITL gate: sets pending_action if anomalies + !approved
                          Guards create_ticket_from_anomaly with hasattr() check
      → synthesizer    ← LiteLLM (Groq primary) + string fallback
      → post_hook      ← execution_ms, audit log
      → END
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
# Uses config singleton — no AppConfig() re-instantiation per call
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
# NOT applied to: capacity_node, rule_node (internal services)
```

---

## Human-in-the-Loop (nodes.py — auto_ticket_node)
```
Flow:
  1st call (approved=False):  anomalies found → set pending_action → skip tickets
  2nd call (approved=True):   create Jira tickets → clear pending_action
                               If CapacityAgent unconfigured → pending_action.error set

Critical keywords that trigger HITL: threshold, missing, below, risk, drop, fail

Streamlit: _render_hitl_panel() checks st.session_state.pending_hitl
Teams:     build_hitl_card() renders Approve/Reject Action.Submit buttons
           User clicks → invoke Activity → _handle_invoke() → re-run graph (approved=True)
```

---

## FastAPI Endpoints (api/app.py)
```
GET  /health             → liveness probe (no rate limit)
POST /query              → JSON response, 20/min per IP
POST /query/stream       → SSE: start → result → done events, 20/min per IP
GET  /history/{thread}   → conversation history from checkpointer, 60/min
GET  /agents/status      → Redis + agents + daily token usage, 120/min
POST /teams/webhook      → Teams bot, 10/min per X-User-Id
GET  /teams/health       → Teams bot probe
POST /ingest             → multipart upload → triggers Airflow on_demand DAG, 10/min

Run: uv run uvicorn src.api.app:app --reload --port 8000
```

---

## Teams Bot (teams/)
```
Files:
  teams/models.py  — TeamsActivity (model_config Pydantic V2), TeamsUser, TeamsConversation
  teams/cards.py   — build_response_card(), build_hitl_card(), build_error_card(),
                     build_welcome_card(), build_thinking_card()
  teams/bot.py     — FastAPI router, HMAC verification, activity routing
                     mock_mode derived from ENABLE_MOCK env var (not config object)

Activity routing:
  message            → _handle_message() → LangGraph → Adaptive Card
  invoke             → _handle_invoke()  → re-run graph (approve/reject HITL)
  conversationUpdate → _handle_conversation_update() → welcome card

Rate limit: user_limiter (X-User-Id header) — all Teams traffic = same IP
HMAC:       TEAMS_APP_SECRET env var (blank = disabled in dev)
```

---

## Token Budget Guard (core/llm_guard.py)
```python
DAILY_TOKEN_LIMIT = 2_000_000
# Redis key: "token_usage:2024-01-15" (auto-expires 86400s)
# check_and_record_tokens(redis, tokens) → True/False
# get_daily_usage(redis) → {tokens_used, limit, pct, remaining}
# Fail-open: Redis error → return True (never blocks traffic)
```

---

## Services Layer (services/)
```
Design: Interface protocol → Factory → Real or Mock implementation
Switching: ENABLE_MOCK=true (default) → mock; ENABLE_MOCK=false → real with graceful fallback

services/base.py         → 4 runtime_checkable Protocol classes
services/factory.py      → get_data_service(), get_ticket_service(),
                           get_metadata_service(), get_vector_service()
                           Each: checks ENABLE_MOCK → returns mock or tries real
                           → falls back to mock on EnvironmentError (missing creds)
```

### IDataService (databricks/)
```python
# Protocol methods:
query(sql: str) → List[Dict]

# Real:  DatabricksService(config) — raises EnvironmentError if DATABRICKS_* missing
# Mock:  MockDatabricksService(low_grr=False)
#          low_grr=True → GRR=78% row, triggers anomaly detection (HITL tests)
#          Table routing: parses FROM clause, returns canned rows per analytics table
```

### ITicketService (jira/)
```python
# Protocol methods:
search_issues(jql, max_results) → List[Dict]
create_issue(summary, description, issue_type, priority, labels) → Dict  # must include "key"

# Real:  JiraService() — raises EnvironmentError if JIRA_BASE_URL/TOKEN/EMAIL missing
# Mock:  MockJiraService()
#          .tickets list — inspectable after agent.execute() for test assertions
#          Keys auto-increment: DGC-201, DGC-202, ...
```

### IMetadataService (collibra/)
```python
# Protocol methods:
search_assets(name) → List[Dict]
get_asset(asset_id) → Dict
get_data_quality(asset_id) → Dict  # {score, passed, failed, total_rules}

# Real:  CollibraService() — raises EnvironmentError if COLLIBRA_BASE_URL + creds missing
# Mock:  MockCollibraService()
#          4 canned assets: retention, bookings, cac, ltv
#          Broad search fallback: unmatched query returns all 4 assets
```

### IVectorService (pgvector/)
```python
# Protocol methods:
similarity_search(query, k=5) → List[Tuple[Document, float]]  # score 0.0–1.0

# Real:  PGVectorService(config) — raises EnvironmentError if OPENAI_API_KEY or POSTGRES_* missing
# Mock:  NullVectorService()
#          6 governance docs, keyword-scored 0.75–0.95
#          All scores pass KnowledgeAgent's 0.70 threshold
```

---

## Agents (thin wrappers — injection pattern)
```python
# All 4 agents follow this pattern:
class SomeAgent(BaseAgent):
    def __init__(self, config=None, some_service: ISomeService = None):
        self._svc = some_service or get_some_service(config)  # factory if not injected

# Tests inject directly — no patch() needed:
agent = CapacityAgent(ticket_service=MockJiraService())
agent = InformationAgent(data_service=MockDatabricksService())
agent = MetadataAgent(metadata_service=MockCollibraService())
agent = KnowledgeAgent(vector_service=NullVectorService())
```

### InformationAgent
```python
# _detect_products(query) → keyword mapping to ["retention","bookings","cac","ltv"]
# _fetch_metrics(product, time_range) → queries IDataService, returns one row
# _detect_anomalies(product, metrics) → threshold checks per product
# result.data = {"metrics": {product: row_dict}, "anomalies": [str, ...]}
# confidence = 0.95
```

### CapacityAgent
```python
# Uses: ITicketService + get_mcp_tools("jira") (layered on top, optional)
# MCP takes priority for fetch/create when USE_MCP=true
# create_ticket_from_anomaly(anomaly_description, product, priority) → AgentResult
#   Called by auto_ticket_node after HITL approval
# confidence = 0.90 (read) / 0.95 (create)
```

### MetadataAgent
```python
# Uses: IMetadataService + get_mcp_tools("collibra") (layered on top, optional)
# _resolve_products(query) → alias map (churn→retention, arr→bookings, etc.)
# result.data = {product: {asset_id, asset_name, domain, status, owner, steward, data_quality}}
# confidence = 0.93
```

### KnowledgeAgent
```python
# Uses: IVectorService
# RELEVANCE_THRESHOLD = 0.70
# result.data = {"knowledge": [{"topic", "definition", "source"}, ...]}
# confidence = avg score of relevant docs
```

---

## core/vector_store.py (backwards-compat shim)
```python
# get_vector_store(config) → _ServiceAdapter wrapping get_vector_service()
# similarity_search(store, query, k) → delegates to IVectorService
# _ServiceAdapter exposes similarity_search_with_relevance_scores() (legacy method name)
# Existing imports from core.vector_store still work — no changes needed in graph/nodes.py
```

---

## RuleAgent (agents/rule_agent.py)
```python
# _execute dispatch order:
#   1. create keywords  → _create_rule()     (returns dict in result.data)
#   2. evaluate keywords → _evaluate_rules() (result.metadata has "passed"/"failed"/"skipped")
#   3. list keywords    → _list_rules()      (result.data is a list)
#   4. default          → _list_rules()
#
# "skipped" count is set when Databricks is not configured
# metadata = {"passed": N, "failed": N, "skipped": N}
# passed + failed + skipped == len(result.data)  ← test invariant
```

---

## MCP Client (core/mcp_client.py)
```python
get_mcp_tools(server_name: str) → List   # [] when disabled or unavailable
is_mcp_enabled() → bool
list_configured_servers() → List[str]

# Env: USE_MCP=false (default) → always returns []
#      USE_MCP=true + COLLIBRA_MCP_SERVER=/path/to/bin → loads tools via stdio
# Imported at module level in capacity_agent.py and metadata_agent.py
```

---

## Settings (config/settings.py)
```python
@dataclass
class VectorDBConfig:
    # All fields use field(default_factory=lambda: os.getenv(...))
    host:     str = field(default_factory=lambda: os.getenv("POSTGRES_HOST", "localhost"))
    port:     int = field(default_factory=lambda: int(os.getenv("POSTGRES_PORT", "5432")))
    ...

@dataclass
class RedisConfig:
    host: str = field(default_factory=lambda: os.getenv("REDIS_HOST", "localhost"))

@dataclass
class AppConfig:
    environment: str  # development | production
    llm:         LLMConfig
    databricks:  DatabricksConfig
    redis:       RedisConfig
    vector_db:   VectorDBConfig
    # NOTE: AppConfig has NO enable_mock field — use os.getenv("ENABLE_MOCK", "true")
```

---

## Data Products
| Key | Table | Owner |
|---|---|---|
| retention | analytics.retention_metrics | Customer Success |
| bookings | analytics.bookings_fact | Revenue Operations |
| cac | analytics.cac_metrics | Marketing Analytics |
| ltv | analytics.customer_ltv | Data Science |

---

## Airflow RAG Ingestion Pipeline (Day 19)

### src/ingestion/ module
```python
# loaders.py
load_document(path: str) → List[Document]
# Dispatcher by extension:
#   .pdf  → PyPDFLoader  |  .docx → Docx2txtLoader
#   .pptx → UnstructuredPowerPointLoader  |  .xlsx → UnstructuredExcelLoader
#   .txt/.md → TextLoader  |  Raises ValueError for unsupported extensions

# chunker.py
chunk_documents(docs, chunk_size=512, chunk_overlap=64) → List[Document]
# RecursiveCharacterTextSplitter
# Enriches metadata: source, product (from filename), topic, chunk_index,
#                    content_hash (SHA-256) — dedup key

# embedder.py
embed_chunks(chunks: List[Document]) → List[List[float]]
# OpenAIEmbeddings(model="text-embedding-3-small"), batch_size=100
# Returns 1536-dim vectors, parallel to input chunks

# store.py
upsert_chunks(chunks, embeddings, config: VectorDBConfig) → int
# Checks content_hash against existing rows → skip duplicates
# Batch-inserts new chunks via langchain_postgres.PGVector
# Returns count of newly inserted chunks (0 = all duplicates)
```

### 4 Airflow DAGs
```
file_ingestion_dag.py      schedule=None  (FileSensor on AIRFLOW_DOCS_PATH)
  FileSensor → load_docs → chunk → embed → upsert → notify

on_demand_ingest_dag.py    schedule=None  (REST API / POST /ingest)
  conf["filepath"] → load_single → chunk → embed → upsert

collibra_sync_dag.py       schedule="0 6 * * *"  (daily 06:00 UTC)
  fetch_collibra → format_as_documents → chunk → embed → upsert

nightly_refresh_dag.py     schedule="0 2 * * *"  (nightly 02:00 UTC)
  scan_docs → diff_hashes → re_embed_delta → upsert → prune_deleted
```

**Key design decisions:**
- DAGs import from `src/ingestion/` via `PYTHONPATH=/opt/airflow/src` in Dockerfile.airflow
- `content_hash` = SHA-256 of raw chunk text — prevents re-embedding unchanged content
- `product` inferred from filename: `retention_*.pdf` → `"retention"`, etc.
- Airflow connections: `postgres_default` (shared DB), `openai_default` (API key via Variable)
- `docs/` folder: dev = local bind mount; prod = S3 path polled by S3KeySensor

---

## Complete Bug Fix Log

### Days 1–18 (original fixes)
| # | File | Bug | Fix |
|---|---|---|---|
| 1 | `graph/nodes.py` | `result.data.get()` → `AttributeError` when data is None | `data = (result.data or {}) if result.success else {}` |
| 2 | `agents/knowledge_agent.py` | Wrong method name, syntax errors | Full rewrite |
| 3 | `api/middleware.py` | slowapi always used Redis → `ConnectionRefusedError` | Probe Redis at startup; fall back to `memory://` |
| 4 | `api/app.py` | SSE events missing `\n\n` terminator | Added `\n\n` to all 4 `yield` statements |
| 5 | `config/settings.py` | `AppConfig.environment` field missing | Added field |
| 6 | `tests/test_day15.py` | `retry_agent_call` not in scope after monkeypatch | Re-import after monkeypatch |
| 7 | `agents/knowledge_agent.py` | `config` required positional arg | `config: Optional[Any] = None` |
| 8 | `agents/knowledge_agent.py` | Data key `"entries"` | Renamed to `"knowledge"` |
| 9 | `agents/rule_agent.py` | `"evaluate all rules"` matched list branch first | Move evaluate check before list check |
| 10 | `agents/rule_agent.py` | `"create a business rule"` not triggering `_create_rule()` | Added `"create a business"` keyword |
| 11 | `config/settings.py` | `REDIS_HOST` default `"redis"` breaks local dev | Default → `"localhost"` |
| 12 | `tests/test_day14.py` | Cache tests hit live Redis | Force `_client = None` |
| 13 | `tests/test_day14.py` | LLM factory tests crash without API keys | `pytest.skip()` |
| 14 | `tests/test_day14.py` | Flaky cache timing assertion | Assert `final_summary != ""` |
| 15 | `tests/test_rule_agent.py` | Supervisor import from missing path | `pytest.skip()` |

### Validation session fixes
| # | File | Bug | Fix |
|---|---|---|---|
| 16 | `agents/capacity_agent.py` | `get_mcp_tools` local import → `patch()` AttributeError | Moved to module level |
| 17 | `agents/metadata_agent.py` | Same local import → 11 test errors | Moved to module level |
| 18 | `agents/knowledge_agent.py` | `get_vector_store` + `similarity_search` local imports | Moved to module level |
| 19 | `graph/nodes.py` | `auto_ticket_node` called `create_ticket_from_anomaly` on `_UnconfiguredAgent` | Added `hasattr()` guard |
| 20 | `teams/bot.py` | `config.enable_mock` — field doesn't exist on `AppConfig` | Replaced with `os.getenv("ENABLE_MOCK", "true")` |
| 21 | `teams/models.py` | Pydantic V2: `class Config:` deprecated | Replaced with `model_config = {"populate_by_name": True}` |
| 22 | `api/app.py` | `asyncio.get_event_loop()` deprecated Python 3.10+ | `asyncio.get_running_loop()` |
| 23 | `teams/bot.py` | Same `asyncio.get_event_loop()` | Same fix |
| 24 | `tests/test_day18.py` | Checked `"docs"` + `"scores"` keys | Fixed to check `"knowledge"` |
| 25 | `tests/test_rule_agent.py` | `passed + failed == len(result.data)` fails when skipped | `passed + failed + skipped == len(result.data)` |
| 26 | `tests/test_day14.py` | Asserted `host == "redis"` | Assert `os.getenv("REDIS_HOST", "localhost")` |
| 27 | `tests/test_day15.py` | HITL approval asserted `pending_action is None` | Loosened: assert `auto_tickets` is a list |
| 28 | multiple | `datetime.utcnow()` deprecated Python 3.12 | `datetime.now(timezone.utc)` throughout |
| 29 | `config/settings.py` `VectorDBConfig` | Fields evaluated at class-definition time | `field(default_factory=lambda: os.getenv(...))` |
| 30 | `core/cache.py` | `AppConfig()` re-instantiated on every cache call | Use config singleton |
| 31 | `pyproject.toml` | `integration` mark unregistered | Added to `[tool.pytest.ini_options] markers` |
| 32 | `requirements.txt` | Contradictory chromadb/faiss-cpu entries | Cleaned up |

### Services refactor fixes
| # | File | Bug | Fix |
|---|---|---|---|
| 33 | `agents/capacity_agent.py` | Fields mapped `issuetype.name` but MockJiraService nests correctly | Defensive `.get()` chain for all nested fields |
| 34 | `tests/test_day18.py` | Imported `_NullVectorStore` from `core.vector_store` (removed) | Now imports `NullVectorService` from `services.pgvector.mock` |
| 35 | `tests/test_day18.py` | `isinstance(store, NullVectorService)` fails on `_ServiceAdapter` wrapper | Unwrap via `getattr(store, "_svc", store)` before isinstance check |

---

## Current Status
**Day 19 Complete — Test suite: 195 passed, 4 skipped, 0 failed, 0 warnings**

### What's done (Days 1–19):
- **Day 1–4**: Project setup, config, logging, base_agent contract
- **Day 5**: Review
- **Day 6**: InformationAgent (Databricks mock)
- **Day 7**: KnowledgeAgent (RAG/pgvector mock)
- **Day 8**: MetadataAgent (Collibra REST mock)
- **Day 9**: CapacityAgent (Jira API mock)
- **Day 10**: RuleAgent (rule registry CRUD)
- **Day 11**: Write capabilities across agents
- **Day 12**: LangGraph StateGraph + SQLite memory + Streamlit UI
- **Day 13**: Groq/GPT-4o intent + synthesizer + pre/post hooks + guardrails + LangSmith
- **Day 14**: LiteLLM fallback chain + Redis cache + @cached_node + RedisConfig
- **Day 15**: retry.py + HITL pending_action in auto_ticket_node + Streamlit HITL panel
- **Day 16**: FastAPI REST server + SSE streaming + slowapi rate limiting + llm_guard.py
- **Day 17**: Teams bot + Adaptive Cards + HMAC verification + HITL approve/reject buttons
- **Day 18**: pgvector + NullVectorStore + MCP client factory + VectorDBConfig + UI polish
- **Validation**: 32 bugs fixed across 12 source files + 5 test files + 2 config files
- **Services Refactor**: Interface layer + mock/real split + factory + agent injection + 33 new tests
- **Day 19**: Docker + CI/CD + Airflow RAG ingestion pipeline (4 DAGs + ingestion module)

### 8 Additional Features — Final Status
| Feature | Status | Day |
|---|---|---|
| Persistence memory | ✅ Done | Day 12 |
| Node caching (Redis) | ✅ Done | Day 14 |
| Pre/post hooks | ✅ Done | Day 13 |
| Error handling & retries | ✅ Done | Day 15 |
| Human-in-the-loop | ✅ Done | Day 15 |
| Logging & monitoring (LangSmith) | ✅ Done | Day 13 |
| Guardrails | ✅ Done | Day 13 |
| MCP integration | ✅ Done | Day 18 |
| RAG ingestion pipeline | ✅ Done | Day 19 |

### Remaining
| Day | Focus | Key deliverables |
|---|---|---|
| **Day 20** | Full system run + cleanup | Smoke tests, pytest coverage ≥ 80%, production cleanup, final context update |

---

## How to Run
```bash
# Install dependencies
uv pip install -r requirements.txt

# Run Streamlit UI only
uv run streamlit run src/ui/app.py

# Run FastAPI server (includes Teams bot at /teams/webhook)
uv run uvicorn src.api.app:app --reload --port 8000

# Run all tests
uv run pytest tests/ -v

# Run only unit tests (skip integration)
uv run pytest tests/ -v -m "not integration"

# Run with Docker (Redis + Postgres + Airflow)
docker compose up
docker compose up airflow-webserver airflow-scheduler   # ingestion only

# Trigger ingestion manually
bash scripts/trigger_ingest.sh path/to/doc.pdf          # via Airflow REST API
curl -X POST http://localhost:8000/ingest -F "file=@doc.pdf"  # via FastAPI
```

---

## Full Environment Variables (.env)
```
# ── Core ───────────────────────────────────────────────────────────────
OPENAI_API_KEY=sk-...          # required for pgvector embeddings (ingestion + query)
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile
GROQ_API_KEY=gsk_...
ENABLE_MOCK=true               # true → all mock services; false → real (with fallback)
DEBUG=false
LOG_LEVEL=INFO
ENVIRONMENT=development

# ── LangSmith ──────────────────────────────────────────────────────────
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_PROJECT=data-governance-copilot

# ── Redis ──────────────────────────────────────────────────────────────
REDIS_HOST=localhost            # use "redis" inside docker compose
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_ENABLED=true

# ── LiteLLM fallbacks ──────────────────────────────────────────────────
ANTHROPIC_API_KEY=
GEMINI_API_KEY=

# ── PostgreSQL + pgvector ──────────────────────────────────────────────
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=governance_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=

# ── Airflow ────────────────────────────────────────────────────────────
AIRFLOW__CORE__EXECUTOR=LocalExecutor
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://postgres:${POSTGRES_PASSWORD}@postgres:5432/airflow_db
AIRFLOW__CORE__FERNET_KEY=           # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
AIRFLOW__WEBSERVER__SECRET_KEY=      # random string
AIRFLOW_ADMIN_USER=admin
AIRFLOW_ADMIN_PASSWORD=admin
AIRFLOW_DOCS_PATH=./docs

# ── Ingestion ──────────────────────────────────────────────────────────
INGESTION_CHUNK_SIZE=512
INGESTION_CHUNK_OVERLAP=64
INGESTION_EMBEDDING_MODEL=text-embedding-3-small
INGESTION_BATCH_SIZE=100

# ── Teams Bot ──────────────────────────────────────────────────────────
TEAMS_APP_SECRET=              # blank = HMAC disabled in dev

# ── MCP ────────────────────────────────────────────────────────────────
USE_MCP=false
COLLIBRA_MCP_SERVER=
JIRA_MCP_SERVER=

# ── Databricks ─────────────────────────────────────────────────────────
DATABRICKS_HOST=
DATABRICKS_TOKEN=
DATABRICKS_HTTP_PATH=

# ── Jira ───────────────────────────────────────────────────────────────
JIRA_BASE_URL=
JIRA_API_TOKEN=
JIRA_EMAIL=
JIRA_PROJECT_KEY=DGC

# ── Collibra ───────────────────────────────────────────────────────────
COLLIBRA_BASE_URL=
COLLIBRA_USERNAME=
COLLIBRA_PASSWORD=
COLLIBRA_API_TOKEN=

# ── FastAPI ────────────────────────────────────────────────────────────
CORS_ORIGINS=*
MAX_WORKERS=4

# ── Memory ─────────────────────────────────────────────────────────────
SQLITE_PATH=./data/memory.db
```

---

## Key File Summaries (quick reference)

### services/factory.py
```python
get_data_service(config)     → IDataService    # MockDatabricksService or DatabricksService
get_ticket_service(config)   → ITicketService  # MockJiraService or JiraService
get_metadata_service(config) → IMetadataService # MockCollibraService or CollibraService
get_vector_service(config)   → IVectorService  # NullVectorService or PGVectorService
# All: check ENABLE_MOCK env var; fallback to mock on EnvironmentError
```

### services/jira/mock.py
```python
MockJiraService()
  .search_issues(jql) → 3 canned open incidents (DGC-101/102/103)
  .create_issue(...)  → stores in .tickets list, returns {key: "DGC-NNN", fields: {...}}
  .tickets            → inspectable list of created tickets (for test assertions)
```

### services/databricks/mock.py
```python
MockDatabricksService(low_grr=False)
  .query(sql) → parses FROM clause, returns canned rows for that analytics table
  low_grr=True → retention rows have GRR=78% (< 85% threshold → triggers anomaly)
```

### core/cache.py
```python
get_client(config)                    # connect Redis, return None if unavailable
make_key(prefix, **kwargs)            # SHA-256 cache key
cache_get(client, key)                # get from Redis or in-memory fallback
cache_set(client, key, value, ttl)    # set with TTL
invalidate_pattern(client, pattern)   # bulk delete by glob pattern
@cached_node(prefix, ttl)            # decorator — uses config singleton
```

### core/retry.py
```python
@with_retry(max_retries, backoff_factor, exceptions)   # decorator
retry_agent_call(agent.execute, request, max_retries)  # returns AgentResult(success=False) on failure
```

### core/vector_store.py
```python
# Backwards-compat shim — delegates to services/pgvector/
get_vector_store(config) → _ServiceAdapter (wraps IVectorService)
similarity_search(store, query, k=5) → List[Tuple[Document, float]]
# _ServiceAdapter.similarity_search_with_relevance_scores() = legacy method name
```

### teams/cards.py
```python
build_response_card(result)                              # main answer card
build_hitl_card(pending_action, thread_id, query)        # approve/reject buttons
build_error_card(message)                                # red error card
build_welcome_card()                                     # bot added to channel
build_thinking_card()                                    # processing placeholder
```

---

## Instructions for New Chat
1. Paste this entire file at the start of the chat
2. Upload your codebase zip (optional but recommended)
3. Say **"Day 20"** to continue with full system run + cleanup
4. At end of each session ask: **"Update my context file for today"**
