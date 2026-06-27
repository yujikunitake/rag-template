# rag-template

Modular RAG template with configurable chunking, embedding, and reranking,
a staging system for A/B pipeline comparison, and a document management UI.

## Stack

- **Backend:** Python 3.11 · FastAPI · PostgreSQL + pgvector · Alembic
- **Embedding:** `nomic-embed-text-v1.5` (local, MPS) · OpenAI (pluggable)
- **Reranking:** InRanker (Unicamp, PT/EN) · CrossEncoder (pluggable)
- **LLM:** OpenRouter (DeepSeek default, complexity-routed)
- **Frontend:** React · Vite · TailwindCSS · shadcn/ui

## Quickstart

```bash
# 1. Start the database
docker compose up -d

# 2. Install dependencies
uv sync --extra dev

# 3. Copy environment variables
cp .env.example .env
# Edit .env with your keys

# 4. Export environment and run migrations
set -a && source .env && set +a
uv run alembic upgrade head

# 5. Start the API
uv run uvicorn src.main:app --reload --port 8000
```

## Configuration

The project uses two separate configuration mechanisms with different responsibilities.

**`config.yaml`** — pipeline behaviour (versioned, committed to the repo):

```yaml
chunker:
  strategy: fixed_size  # fixed_size | recursive | semantic | sliding_window
  chunk_size: 512
  overlap: 64

embedder:
  model: nomic-embed-text-v1.5
  device: mps            # mps (Apple Silicon) | cpu | cuda

retriever:
  strategy: vector       # vector | hybrid | mmr
  top_k: 5
  mmr_lambda: 0.5

reranker:
  enabled: false
  model: unicamp-dl/InRanker-small

generator:
  provider: openrouter
  default_model: deepseek/deepseek-chat-v3
  fallback_model: google/gemini-flash-1.5
```

**`.env`** — secrets and environment-specific overrides (never committed):

```bash
# API keys
OPENROUTER_API_KEY=your-key
OPENAI_API_KEY=your-key        # only if using OpenAI embedder

# Database
DATABASE_URL=postgresql://rag:rag@localhost:5432/rag_db

# Auth
JWT_SECRET_KEY=change-me-to-a-random-secret
```

Any `config.yaml` field can be overridden at runtime via environment variable
using the pattern `SECTION__FIELD`. This is useful for deploying on servers
where `mps` is not available:

```bash
EMBEDDER__DEVICE=cpu uv run uvicorn src.main:app --port 8000
```

## Development

```bash
uv run pytest tests/ -v --cov=src   # run tests
uv run ruff check src/ tests/        # lint
uv run mypy src/                     # type check
```
