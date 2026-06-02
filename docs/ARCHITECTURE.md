# JARVIS Architecture

## System Overview

JARVIS is a multi-agent AI intelligence operating system built for Reddit community builders and researchers.

## Architecture Layers

```
┌─────────────────────────────────────────────────┐
│              Next.js Frontend (Port 3000)        │
│  Dashboard · Research · Reddit · Security ·      │
│  Memory · Reports · Settings                     │
└───────────────────┬─────────────────────────────┘
                    │ HTTP/REST
┌───────────────────▼─────────────────────────────┐
│            FastAPI Backend (Port 8000)            │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │  Auth    │  │  Reddit  │  │  Research    │   │
│  │  Routes  │  │  Routes  │  │  Routes      │   │
│  └──────────┘  └──────────┘  └──────────────┘   │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ Security │  │  Memory  │  │  Reports     │   │
│  │  Routes  │  │  Routes  │  │  Routes      │   │
│  └──────────┘  └──────────┘  └──────────────┘   │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │         Agent Orchestration Layer           │ │
│  │  Reddit · Research · Security · Strategy   │ │
│  │  Memory · Report agents                    │ │
│  └────────────────────┬────────────────────────┘ │
│                       │                           │
│  ┌────────────────────▼────────────────────────┐ │
│  │              AI Service Layer               │ │
│  │    Anthropic Claude API (primary)           │ │
│  │    OpenAI API (fallback/embeddings)         │ │
│  └─────────────────────────────────────────────┘ │
└───────────────────┬─────────────────────────────┘
                    │
    ┌───────────────┼──────────────┐
    ▼               ▼              ▼
┌───────┐    ┌──────────┐   ┌──────────┐
│Postgres│   │ ChromaDB │   │  Redis   │
│ (main │   │ (vector  │   │ (cache   │
│  DB)  │   │  store)  │   │  queue)  │
└───────┘   └──────────┘   └──────────┘
```

## Agents

| Agent | Responsibility |
|-------|---------------|
| **Reddit Agent** | PRAW API calls, subreddit analysis, topic discovery |
| **Research Agent** | Multi-source research orchestration |
| **Security Agent** | OSINT collection, threat analysis |
| **Strategy Agent** | Decision analysis, option evaluation |
| **Memory Agent** | ChromaDB vector storage, semantic retrieval |
| **Report Agent** | PDF/MD/HTML report generation |
| **Orchestrator** | Intent routing, agent coordination |

## Data Flow

1. User submits request via frontend
2. FastAPI route validates and creates DB record
3. Background task spawned
4. Relevant service/agent runs
5. AI Service (Claude) synthesizes results
6. Results stored in PostgreSQL
7. Vector embeddings stored in ChromaDB
8. Frontend polls for completion

## Database

- **PostgreSQL 15** — primary data store with JSONB for flexible schemas
- **ChromaDB** — vector embeddings for semantic memory search
- **Redis** — caching and rate limiting

## Security

- JWT access tokens (30 min) + refresh tokens (7 days)
- bcrypt password hashing
- Request ID tracking for audit logs
- Rate limiting per user
- CORS with allowlist
