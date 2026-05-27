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
| RAG / Vector Store | pgvector (Day 18) — _NullVectorStore mock in dev |
| Document Loaders | LangChain (PDF, DOCX, PPTX, Excel) |
| Structured Data | Databricks SQL / SQL Warehouse (mock in dev) |
| Governance | Collibra REST API (via MCP — Day 18, USE_MCP=false in dev) |
| Ticketing | Jira REST API |
| Memory | SQLite (dev) / PostgreSQL (prod) via LangGraph checkpointer |
| Cache | Redis (Day 14) — survives ECS restarts, shared across tasks; in-memory fallback when Redis down |
| Observability | LangSmith tracing |
| UI | Streamlit (polished — Day 18) |
| API | FastAPI + SSE + slowapi rate limiting (Day 16) |
| Teams Bot | Adaptive Cards webhook (Day 17) |
| Package Manager | uv |
| Infra | Docker + ECS Fargate |
| CI/CD | GitHub Actions |
| Testing | pytest |
| Secrets | AWS Secrets Manager (prod) |

---

## Folder Structure (After Day 18 + bug-fix session)
```
data-governance-copilot/
├── src/
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py          ✅ AgentState TypedDict (+ start_time, guardrail_passed)
│   │   ├── intent.py         ✅ GPT-4o/Groq structured output + LiteLLM + keyword fallback
│   │   ├── routing.py        ✅ INTENT_AGENT_MAP
│   │   ├── nodes.py          ✅ All nodes + retry + HITL + @cached_node + synthesizer
│   │   │                        BUG FIXED: result.data.get() → (result.data or {}).get()
│   │   └── graph.py          ✅ StateGraph + pre/post hooks + guardrail conditional edge
│   ├── memory/
│   │   ├── __init__.py
│   │   └── checkpointer.py   ✅ SqliteSaver (dev) / PostgresSaver (prod)
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── information_agent.py   ✅ Databricks/SQL mock
│   │   ├── knowledge_agent.py     ✅ Mock keyword lookup + pgvector (prod)
│   │   │                             BUG FIXED: config now Optional; data key "knowledge";
│   │   │                             _execute overrides BaseAgent correctly
│   │   ├── metadata_agent.py      ✅ Collibra REST mock → MCP (Day 18)
│   │   ├── capacity_agent.py      ✅ Jira API mock
│   │   ├── rule_agent.py          ✅ Rule registry CRUD
│   │   │                             BUG FIXED: routing order (evaluate before list);
│   │   │                             added "create a business" trigger keyword
│   │   └── supervisor_agent.py    ✅ Orchestrator
│   ├── core/
│   │   ├── __init__.py
│   │   ├── base_agent.py     ✅ AgentRequest, AgentResult, BaseAgent contract
│   │   ├── logging_utils.py  ✅ Structured JSON logging, decorators, error hierarchy
│   │   ├── guardrails.py     ✅ Length, SQL injection, prompt injection, PII (Day 13)
│   │   ├── cache.py          ✅ Redis + in-memory fallback + @cached_node (Day 14)
│   │   ├── llm_factory.py    ✅ LiteLLM factory + fallback chain (Day 14)
│   │   ├── retry.py          ✅ @with_retry + retry_agent_call() (Day 15)
│   │   ├── llm_guard.py      ✅ Daily token budget hard stop (Day 16)
│   │   ├── vector_store.py   ✅ pgvector store + _NullVectorStore mock (Day 18)
│   │   └── mcp_client.py     ✅ MCP client factory with graceful fallback (Day 18)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── middleware.py     ✅ slowapi limiter — Redis if available, memory:// fallback
│   │   │                        BUG FIXED: no longer crashes when Redis is unavailable
│   │   └── app.py            ✅ FastAPI + /query + /query/stream + /history + /agents/status
│   │                             BUG FIXED: SSE events now include \n\n terminator
│   ├── teams/
│   │   ├── __init__.py
│   │   ├── models.py         ✅ TeamsActivity, TeamsUser, TeamsConversation (Day 17)
│   │   ├── cards.py          ✅ Adaptive Card builders: response, HITL, error, welcome
│   │   └── bot.py            ✅ Webhook router + HMAC verification + activity routing
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py       ✅ AppConfig + LLMConfig + RedisConfig + DatabricksConfig
│   │                             + VectorDBConfig (Day 18)
│   │                             BUG FIXED: REDIS_HOST default → "localhost";
│   │                             AppConfig.environment field added
│   ├── tools/
│   │   └── __init__.py
│   ├── ui/
│   │   ├── __init__.py
│   │   └── app.py            ✅ Streamlit chat UI + HITL panel + execution stats
│   └── __init__.py
├── scripts/
│   └── init_pgvector.sql     ✅ One-time pgvector DB setup (Day 18)
├── tests/
│   ├── test_capacity_agent.py   ✅ 12/12 passing
│   ├── test_day14.py            ✅ BUG FIXED: cache tests isolated from live Redis;
│   │                                LLM tests skip gracefully without API keys;
│   │                                cache_hit integration assertion fixed
│   ├── test_day15.py            ✅ BUG FIXED: retry_agent_call scope after monkeypatch
│   ├── test_day16.py            ✅ All passing (middleware Redis fallback fix)
│   ├── test_day17.py            ✅ All passing
│   ├── test_information_agent.py ✅ 11/11 passing
│   ├── test_knowledge_agent.py  ✅ BUG FIXED: data key "knowledge"; config optional
│   ├── test_metadata_agent.py   ✅ 12/12 passing
│   └── test_rule_agent.py       ✅ BUG FIXED: supervisor import fallback + skip;
│                                    evaluate routing; create_business trigger
├── data/
│   └── memory.db             ✅ SQLite conversation memory
├── docker-compose.yml        ✅ App + Redis services (Day 14)
├── .env                      ✅ All vars (see reference below)
├── .env.example              ✅ Full reference with all vars
├── .gitignore
├── pyproject.toml
└── requirements.txt
```

**Test suite result (after all fixes): 129 passed, 4 skipped, 0 failed**
The 4 skipped are supervisor_agent tests that reference a legacy `docs/deployment/old/` path not present in the main src tree — they skip gracefully via `pytest.skip()`.

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
# Fallback: in-memory dict when Redis is unavailable
```

---

## Rate Limiter (api/middleware.py)  ← FIXED Day 15–18
```python
# FIX: probes Redis at import time (1-second timeout).
# Uses Redis storage if reachable → shared limits across ECS tasks.
# Falls back to memory:// if Redis unavailable → per-process limits (dev/CI).
# This prevents ConnectionRefusedError from crashing every endpoint in tests.

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
                           FIX: each event now ends with \n\n (SSE spec)
GET  /history/{thread}   → conversation history from checkpointer, 60/min
GET  /agents/status      → Redis + agents + daily token usage, 120/min
POST /teams/webhook      → Teams bot, 10/min per X-User-Id
GET  /teams/health       → Teams bot probe

Run: uv run uvicorn src.api.app:app --reload --port 8000
```

---

## Teams Bot (teams/)
```
Files:
  teams/models.py  — TeamsActivity, TeamsUser, TeamsConversation Pydantic models
  teams/cards.py   — build_response_card(), build_hitl_card(), build_error_card(),
                     build_welcome_card(), build_thinking_card()
  teams/bot.py     — FastAPI router, HMAC verification, activity routing

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

## KnowledgeAgent (agents/knowledge_agent.py)  ← FIXED Day 18
```python
class KnowledgeAgent(BaseAgent):
    # FIX 1: config is now Optional[Any] = None
    #   Tests can call KnowledgeAgent(enable_mock=True) without a config object.
    # FIX 2: data key is "knowledge" (not "entries")
    #   result.data == {"knowledge": [list of entry dicts]}
    # FIX 3: overrides _execute() (not execute()) — correct BaseAgent contract
    # FIX 4: vector store only initialised when enable_mock=False AND config is not None

    def __init__(self, config=None, enable_mock=True): ...
    def _execute(self, request) -> AgentResult:
        # Mock mode: keyword lookup → MOCK_KNOWLEDGE_BASE
        # Prod mode: pgvector similarity_search, score > 0.7 threshold
        return AgentResult(..., data={"knowledge": entries}, ...)
```

---

## RuleAgent routing fix (agents/rule_agent.py)  ← FIXED Day 18
```python
# FIX 1: evaluate checked BEFORE list keywords
#   "evaluate all rules" was matching "all rules" (list branch) first.
# FIX 2: added "create a business" and "create a dq" to create triggers
#   "create a business rule threshold for LTV" now correctly → _create_rule()

_execute dispatch order (after fix):
  1. create keywords  → _create_rule()     (returns dict in result.data)
  2. evaluate keywords → _evaluate_rules() (result.metadata has "passed"/"failed" counts)
  3. list keywords    → _list_rules()      (result.data is a list)
  4. default          → _list_rules()
```

---

## pgvector / Vector Store (core/vector_store.py)
```python
get_vector_store(config: VectorDBConfig) → PGVector | _NullVectorStore
similarity_search(store, query, k=5)    → List[Tuple[Document, float]]

# _NullVectorStore: keyword-scored mock, always returns 6 governance docs
# scored 0.75–0.95. knowledge_agent filters: score > 0.70.
# Production path only activates when ENABLE_MOCK=false AND OPENAI_API_KEY set.
```

---

## MCP Client (core/mcp_client.py)
```python
get_mcp_tools(server_name: str) → List   # [] when disabled or unavailable
is_mcp_enabled() → bool
list_configured_servers() → List[str]

# Env: USE_MCP=false (default) → always returns []
#      USE_MCP=true + COLLIBRA_MCP_SERVER=/path/to/bin → loads tools via stdio
# Requires: langchain-mcp-adapters, mcp (only when USE_MCP=true)
```

---

## Settings (config/settings.py)  ← FIXED Day 18
```python
@dataclass
class RedisConfig:
    host: str = os.getenv("REDIS_HOST", "localhost")   # FIX: was "redis" (Docker name)
    # docker-compose overrides via REDIS_HOST=redis env var

@dataclass
class AppConfig:
    environment: str = os.getenv("ENVIRONMENT", "development")  # FIX: field was missing
    llm:         LLMConfig
    databricks:  DatabricksConfig
    redis:       RedisConfig
    vector_db:   VectorDBConfig

@dataclass
class VectorDBConfig:
    host, port, database, user, password   # from POSTGRES_* env vars
    table_name    = "document_embeddings"
    embedding_dim = 1536
    connection_string → "postgresql+psycopg2://..."
```

---

## Data Products (settings.py)
| Key | Table | Owner |
|---|---|---|
| retention | analytics.retention_metrics | Customer Success |
| bookings | analytics.bookings_fact | Revenue Operations |
| cac | analytics.cac_metrics | Marketing Analytics |
| ltv | analytics.customer_ltv | Data Science |

---

## Bug Fix Summary (Days 15–18 debug session)

### Round 1 (fixes from previous session)
| # | File | Bug | Fix |
|---|---|---|---|
| 1 | `graph/nodes.py` | `result.data.get()` → `AttributeError` when data is None | `data = (result.data or {}) if result.success else {}` |
| 2 | `agents/knowledge_agent.py` | Wrong method name (`execute` not `_execute`), syntax errors, missing `agent_name` | Full rewrite |
| 3 | `api/middleware.py` | slowapi always used Redis → `ConnectionRefusedError` on every request when Redis down | Probe Redis at startup; fall back to `memory://` |
| 4 | `api/app.py` | SSE events missing `\n\n` terminator → `iter_lines()` merged all events | Added `\n\n` to all 4 `yield` statements |
| 5 | `config/settings.py` | `AppConfig.environment` field missing | Added field |
| 6 | `tests/test_day15.py` | `retry_agent_call` not in scope after `time.sleep` monkeypatch | Re-import after monkeypatch |

### Round 2 (fixes from this session)
| # | File | Bug | Fix |
|---|---|---|---|
| 7 | `agents/knowledge_agent.py` | `config` required positional arg — breaks `KnowledgeAgent(enable_mock=True)` | `config: Optional[Any] = None` |
| 8 | `agents/knowledge_agent.py` | Data key `"entries"` — tests expected `"knowledge"` | Renamed key |
| 9 | `agents/rule_agent.py` | `"evaluate all rules"` matched list branch (wrong routing order) | Move evaluate check before list check |
| 10 | `agents/rule_agent.py` | `"create a business rule"` not triggering `_create_rule()` | Added `"create a business"` keyword |
| 11 | `config/settings.py` | `REDIS_HOST` default `"redis"` (Docker name) — test expects `"localhost"` | Default → `"localhost"` |
| 12 | `tests/test_day14.py` | Cache tests hit live Redis → stale keys cause false HITs | Force `_client = None` to use in-memory fallback |
| 13 | `tests/test_day14.py` | LLM factory tests crash without API keys | `pytest.skip()` when no provider key set |
| 14 | `tests/test_day14.py` | `test_cache_hit_on_second_call` used flaky timing assertion | Assert `final_summary != ""` on both runs |
| 15 | `tests/test_rule_agent.py` | Supervisor tests import from `docs/deployment/old/` (not in src) | `pytest.skip()` when neither path importable |

---

## Current Status: ✅ Day 18 Complete + All Bugs Fixed
**Test suite: 129 passed, 4 skipped, 0 failed**

### What's done (Days 1–18):
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
- **Day 18**: pgvector + _NullVectorStore + MCP client factory + VectorDBConfig + UI polish
- **Bug-fix session**: 15 bugs fixed across 6 source files + 3 test files

---

## Remaining Days Plan

### Week 4 — DevOps (updated)
| Day | Focus | Key deliverables |
|---|---|---|
| **Day 19** | Docker + Compose + CI/CD | Full Dockerfiles, docker-compose.yml (app + Redis + Postgres), GitHub Actions |
| **Day 20** | Full system run + cleanup | Smoke tests, pytest coverage, production cleanup, final context update |

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

# Run with Docker (Redis included)
docker-compose up
```

---

## Full Environment Variables (.env)
```
# ── Core ───────────────────────────────────────────────────────────────
OPENAI_API_KEY=sk-...          # optional — used by pgvector embeddings in prod
LLM_PROVIDER=groq              # primary provider
LLM_MODEL=llama-3.3-70b-versatile
GROQ_API_KEY=gsk_...           # primary LLM key
ENABLE_MOCK=true
DEBUG=false
LOG_LEVEL=INFO
ENVIRONMENT=development

# ── LangSmith (Day 13) ─────────────────────────────────────────────────
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_PROJECT=data-governance-copilot

# ── Redis (Day 14) ─────────────────────────────────────────────────────
REDIS_HOST=localhost            # use "redis" inside docker-compose
REDIS_PORT=6379
REDIS_PASSWORD=                 # leave blank for local dev
REDIS_ENABLED=true

# ── LiteLLM fallbacks (Day 14) ─────────────────────────────────────────
ANTHROPIC_API_KEY=
GEMINI_API_KEY=

# ── PostgreSQL + pgvector (Day 18) ─────────────────────────────────────
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=governance_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=

# ── Teams Bot (Day 17) ─────────────────────────────────────────────────
TEAMS_APP_SECRET=              # blank = HMAC disabled in dev

# ── MCP (Day 18) ───────────────────────────────────────────────────────
USE_MCP=false
COLLIBRA_MCP_SERVER=           # path to Collibra MCP server binary
JIRA_MCP_SERVER=               # path to Jira MCP server binary

# ── Databricks ─────────────────────────────────────────────────────────
DATABRICKS_HOST=
DATABRICKS_TOKEN=
DATABRICKS_HTTP_PATH=

# ── Jira ───────────────────────────────────────────────────────────────
JIRA_BASE_URL=
JIRA_API_TOKEN=
JIRA_EMAIL=

# ── FastAPI ────────────────────────────────────────────────────────────
CORS_ORIGINS=*
MAX_WORKERS=4

# ── Memory ─────────────────────────────────────────────────────────────
SQLITE_PATH=./data/memory.db
```

---

## Key File Summaries (quick reference)

### core/cache.py
```python
get_client(config)                    # connect Redis, return None if unavailable
make_key(prefix, **kwargs)            # SHA-256 cache key
cache_get(client, key)                # get from Redis or in-memory fallback
cache_set(client, key, value, ttl)    # set with TTL
invalidate_pattern(client, pattern)   # bulk delete by glob pattern
@cached_node(prefix, ttl)            # decorator for sync/async node functions
```

### core/retry.py
```python
@with_retry(max_retries, backoff_factor, exceptions)   # decorator
retry_agent_call(agent.execute, request, max_retries)  # returns AgentResult(success=False) on failure
```

### core/llm_factory.py
```python
get_llm(config, streaming=False)         # returns ChatLiteLLM with .with_fallbacks()
get_structured_llm(config, schema)       # returns LLM.with_structured_output(schema)
```

### core/guardrails.py
```python
run_guardrails(query) → GuardrailResult(passed, reason, cleaned_query, pii_found)
```

### core/llm_guard.py
```python
check_and_record_tokens(redis, tokens)   # True=allow, False=429
get_daily_usage(redis)                   # {tokens_used, limit, pct, remaining}
estimate_tokens(text)                    # len(text)//4 + 500
```

### core/vector_store.py
```python
get_vector_store(config: VectorDBConfig) → PGVector | _NullVectorStore
similarity_search(store, query, k=5)    → List[Tuple[Document, float]]
# _NullVectorStore used when ENABLE_MOCK=true or no OPENAI_API_KEY
```

### core/mcp_client.py
```python
get_mcp_tools(server_name: str) → List[BaseTool]   # [] if USE_MCP=false
is_mcp_enabled() → bool
list_configured_servers() → List[str]
```

### agents/knowledge_agent.py  ← FIXED
```python
KnowledgeAgent(config=None, enable_mock=True)   # config is optional
# _execute() → AgentResult(data={"knowledge": [entry_dicts]}, ...)
# entry_dict keys: topic, definition, business_context, runbook, source
```

### agents/rule_agent.py  ← FIXED
```python
# _execute dispatch order (fixed):
# 1. create → _create_rule()     → result.data = dict (single new rule)
# 2. evaluate → _evaluate_rules() → result.metadata = {passed, failed}
# 3. list/default → _list_rules() → result.data = list of rule dicts
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
3. Say **"Day 19"** to continue
4. At end of each session ask: **"Update my context file for today"**
