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

# 4. Run migrations
uv run alembic upgrade head

# 5. Start the API
uv run uvicorn src.main:app --reload --port 8000
```

## Development

```bash
uv run pytest tests/ -v --cov=src   # run tests
uv run ruff check src/ tests/        # lint
uv run mypy src/                     # type check
```
