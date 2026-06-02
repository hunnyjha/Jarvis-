# JARVIS — Reddit Intelligence AI Operating System

A production-grade personal intelligence operating system for Reddit community
builders, researchers, and growth strategists. JARVIS is **not a chatbot** — it
is a multi-agent system that analyzes subreddits, discovers viral topics,
investigates accounts for manipulation, runs cited research, remembers context
across sessions, and produces strategic recommendations.

## Capabilities

| Module | What it does |
| --- | --- |
| **Reddit Intelligence** | Subreddit growth, engagement, sentiment, topic & keyword analysis |
| **Topic Discovery** | Viral opportunities, niche gaps, recurring pain points |
| **Security Analysis** | Vote manipulation, brigading, sockpuppet & burst-activity detection |
| **Research Agent** | Multi-source research with citations and confidence ratings |
| **Memory System** | Semantic long-term memory backed by ChromaDB vectors |
| **Strategy Agent** | Option A/B/C analysis with pros, cons, risks, effort & impact |

## Architecture

- **Frontend** — Next.js 14 (App Router) · TypeScript · Tailwind · Zustand · React Query
- **Backend** — FastAPI · async SQLAlchemy 2.0 · Pydantic v2 · Alembic
- **Agents** — LangGraph multi-agent graph with intent classification and tool execution
- **Data** — PostgreSQL (relational) · ChromaDB (vectors) · Redis (cache, tokens, rate limits)
- **AI** — Anthropic Claude (primary reasoning) · OpenAI (embeddings)
- **Infra** — Docker Compose · Nginx reverse proxy · Railway (backend) · Vercel (frontend)

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full system design.

## Project layout

```
backend/         FastAPI app, agents, services, models, Alembic migrations
frontend/        Next.js 14 dashboard
nginx/           Production reverse-proxy config
docker-compose.yml        Local dev stack
docker-compose.prod.yml   Production stack
railway.json     Backend deploy config
```

## Quick start (local)

```bash
cp .env.example .env          # fill in ANTHROPIC_API_KEY, REDDIT_CLIENT_ID, etc.
make dev                      # builds & starts postgres, redis, chromadb, backend, frontend
make migrate                  # apply database migrations
make seed                     # create the default admin user + memory collections
```

- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs
- Default admin: `admin@jarvis.local` / `JarvisAdmin2024!`

## Required environment variables

The full list lives in [`.env.example`](.env.example). The essentials:

| Variable | Purpose |
| --- | --- |
| `ANTHROPIC_API_KEY` | Claude reasoning (required) |
| `OPENAI_API_KEY` | Embeddings for memory search |
| `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` | Reddit data access via PRAW |
| `JWT_SECRET_KEY` | Token signing (≥ 32 chars in production) |
| `DATABASE_URL` / `REDIS_URL` / `CHROMADB_URL` | Service connections |

## Development

```bash
make dev        # start the dev stack
make logs       # tail all service logs
make migrate    # alembic upgrade head
make test       # run the backend test suite
make shell-backend  # open a shell in the backend container
make clean      # tear down containers and volumes
```

## Deployment

- **Backend** → Railway (`railway.json` runs `alembic upgrade head && uvicorn`)
- **Frontend** → Vercel (`frontend/vercel.json`)
- **Self-hosted** → `make prod` uses `docker-compose.prod.yml` with Nginx,
  resource limits, and separated internal/public networks.

## Security model

- JWT access tokens (30 min) + rotating refresh tokens (7 days)
- JTI-based token blacklisting in Redis for immediate revocation
- Rate limiting at the Nginx and application layers
- Structured audit logging of sensitive actions
