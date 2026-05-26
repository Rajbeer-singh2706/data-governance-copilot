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
| LLM | GPT-4o via LiteLLM (multi-provider fallback chain) |
| Structured Output | Pydantic + `.with_structured_output()` |
| RAG / Vector Store | pgvector (Day 18) — replacing ChromaDB/FAISS |
| Document Loaders | LangChain (PDF, DOCX, PPTX, Excel) |
| Structured Data | Databricks SQL / SQL Warehouse (mock in dev) |
| Governance | Collibra REST API (via MCP — Day 18) |
| Ticketing | Jira REST API |
| Memory | SQLite (dev) / PostgreSQL (prod) via LangGraph checkpointer |
| Cache | Redis (Day 14) — survives ECS restarts, shared across tasks |
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

## Folder Structure (After Day 17)
```
data-governance-copilot/
├── src/
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py          ✅ AgentState TypedDict (+ start_time, guardrail_passed)
│   │   ├── intent.py         ✅ GPT-4o structured output + LiteLLM + keyword fallback
│   │   ├── routing.py        ✅ INTENT_AGENT_MAP
│   │   ├── nodes.py          ✅ All nodes + retry + HITL + @cached_node + GPT-4o synthesizer
│   │   └── graph.py          ✅ StateGraph + pre/post hooks + guardrail conditional edge
│   ├── memory/
│   │   ├── __init__.py
│   │   └── checkpointer.py   ✅ SqliteSaver (dev) / PostgresSaver (prod)
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── information_agent.py   ✅ Databricks/SQL mock
│   │   ├── knowledge_agent.py     ✅ RAG mock → pgvector (Day 18)
│   │   ├── metadata_agent.py      ✅ Collibra REST mock → MCP (Day 18)
│   │   ├── capacity_agent.py      ✅ Jira API mock
│   │   ├── rule_agent.py          ✅ Rule registry CRUD
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
│   │   ├── vector_store.py   🔜 pgvector store (Day 18)
│   │   └── mcp_client.py     🔜 MCP client factory (Day 18)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── middleware.py     ✅ slowapi limiter setup + user_limiter (Day 16)
│   │   └── app.py            ✅ FastAPI + /query + /query/stream + /history + /agents/status + Teams router (Day 17)
│   ├── teams/
│   │   ├── __init__.py
│   │   ├── models.py         ✅ TeamsActivity, TeamsUser, TeamsConversation (Day 17)
│   │   ├── cards.py          ✅ Adaptive Card builders: response, HITL, error, welcome (Day 17)
│   │   └── bot.py            ✅ Webhook router + HMAC verification + activity routing (Day 17)
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py       ✅ AppConfig + LLMConfig + RedisConfig + DatabricksConfig
│   │                             🔜 + VectorDBConfig (Day 18)
│   ├── tools/
│   │   └── __init__.py
│   ├── ui/
│   │   ├── __init__.py
│   │   └── app.py            ✅ Streamlit chat UI + HITL panel + execution stats (Day 15)
│   │                             🔜 UI polish (Day 18)
│   └── __init__.py
├── scripts/
│   └── init_pgvector.sql     🔜 One-time pgvector DB setup (Day 18)
├── tests/
│   ├── test_day13.py         ✅
│   ├── test_day14.py         ✅
│   ├── test_day15.py         ✅
│   ├── test_day16.py         ✅
│   └── test_day17.py         ✅
├── data/
│   └── memory.db             ✅ SQLite conversation memory
├── docker-compose.yml        ✅ App + Redis services (Day 14)
├── .env                      ✅ All vars (see reference below)
├── .env.example              ✅ Full reference with all vars
├── .gitignore
├── pyproject.toml
└── requirements.txt
```

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
      → synthesizer    ← GPT-4o via get_llm() + LiteLLM fallback
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
# Fallback: keyword matching when OPENAI_API_KEY absent or LLM fails
```

---

## LiteLLM Fallback Chain (llm_factory.py)
```python
# Fallback order (configured in LLMConfig.fallback_models):
gpt-4o → gpt-4o-mini → anthropic/claude-haiku-4-5 → gemini/gemini-1.5-flash

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

## Data Products (settings.py)
| Key | Table | Owner |
|---|---|---|
| retention | analytics.retention_metrics | Customer Success |
| bookings | analytics.bookings_fact | Revenue Operations |
| cac | analytics.cac_metrics | Marketing Analytics |
| ltv | analytics.customer_ltv | Data Science |

---

## ⚡ Production Upgrades Status
| # | Change | Status | Day |
|---|---|---|---|
| 1 | ChromaDB → pgvector | 🔜 In progress | Day 18 |
| 2 | Redis cache | ✅ Done | Day 14 |
| 3 | Rate limiting (slowapi) | ✅ Done | Day 16 |
| 4 | LiteLLM resilience | ✅ Done | Day 14 |

### Change 1 — pgvector (Day 18) — Still to implement:
```
New: src/core/vector_store.py
  get_vector_store(config: VectorDBConfig) → PGVector
  similarity_search(store, query, k=5, filter=None) → List[Tuple[Document, float]]

New: scripts/init_pgvector.sql
  CREATE EXTENSION IF NOT EXISTS vector;
  CREATE TABLE document_embeddings (id UUID, collection TEXT, document TEXT,
    metadata JSONB, embedding vector(1536), created_at TIMESTAMPTZ);
  CREATE INDEX USING ivfflat (embedding vector_cosine_ops) WITH (lists=100);

New: VectorDBConfig in settings.py
  host, port, database, user, password
  table_name = "document_embeddings"
  embedding_dim = 1536
  connection_string property → "postgresql+psycopg2://..."

Update: knowledge_agent.py
  Replace: from langchain_community.vectorstores import FAISS
  With:    from core.vector_store import get_vector_store, similarity_search
  Retrieval: docs = [doc for doc, score in results if score > 0.7]

Add to requirements: pgvector>=0.3.0, psycopg2-binary>=2.9.9,
                     sqlalchemy>=2.0.0, langchain-postgres>=0.0.9
Remove from requirements: chromadb, faiss-cpu
Add to .env: POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
```

---

## Current Status: ✅ Day 17 Complete

### What's done (Days 1–17):
- **Day 1–4**: Project setup, config, logging, base_agent contract
- **Day 5**: Review
- **Day 6**: InformationAgent (Databricks mock)
- **Day 7**: KnowledgeAgent (RAG/FAISS mock)
- **Day 8**: MetadataAgent (Collibra REST mock)
- **Day 9**: CapacityAgent (Jira API mock)
- **Day 10**: RuleAgent (rule registry CRUD)
- **Day 11**: Write capabilities across agents
- **Day 12**: LangGraph StateGraph + SQLite memory + Streamlit UI
- **Day 13**: GPT-4o intent + GPT-4o synthesizer + pre/post hooks + guardrails + LangSmith
- **Day 14**: LiteLLM fallback chain + Redis cache + @cached_node + RedisConfig
- **Day 15**: retry.py + HITL pending_action in auto_ticket_node + app.py HITL panel
- **Day 16**: FastAPI REST server + SSE streaming + slowapi rate limiting + llm_guard.py
- **Day 17**: Teams bot + Adaptive Cards + HMAC verification + HITL approve/reject buttons

---

## Remaining Days Plan

### Week 4 — UI, API, DevOps (updated)
| Day | Focus | Key deliverables |
|---|---|---|
| **Day 18** | pgvector + MCP + UI polish | `vector_store.py`, `init_pgvector.sql`, `VectorDBConfig`, `mcp_client.py`, Streamlit polish |
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
| MCP integration | 🔜 In progress | Day 18 |

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
OPENAI_API_KEY=sk-...
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
ENABLE_MOCK=true
DEBUG=false
LOG_LEVEL=INFO
ENVIRONMENT=development

# ── LangSmith (Day 13) ─────────────────────────────────────────────────
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_PROJECT=data-governance-copilot

# ── Redis (Day 14) ─────────────────────────────────────────────────────
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
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
TEAMS_APP_SECRET=         # blank = HMAC disabled in dev

# ── MCP (Day 18) ───────────────────────────────────────────────────────
USE_MCP=false
COLLIBRA_MCP_SERVER=      # path to Collibra MCP server binary
JIRA_MCP_SERVER=          # path to Jira MCP server binary

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
3. Say **"Day 18"** to continue
4. At end of each session ask: **"Update my context file for today"**
