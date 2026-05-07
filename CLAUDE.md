# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

"随便吃" (Whatever-to-Eat) - A Chinese-language recipe recommendation agent. Users say "随便" (whatever) when asked what to eat, and the agent recommends dishes based on their preferences, dietary restrictions, cooking skill, and recent meal history.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# CLI mode (interactive chat in terminal)
python src/whatever_agent.py

# API server (FastAPI)
uvicorn src.api:app --reload --port 8000

# React frontend (dev server, visit http://localhost:5173)
cd frontend && npm run dev

# Docker (full stack: API + Frontend)
docker compose up --build
```

All commands must run from the project root directory (not inside `src/`).

## Environment Variables

Configure in `.env`:
- `AGENT_API_KEY`, `AGENT_MODEL_ID`, `AGENT_BASE_URL` — LLM config (defaults to DeepSeek Chat)
- `EMBEDDING_API_KEY`, `EMBEDDING_MODEL_ID`, `EMBEDDING_BASE_URL` — Embedding model (defaults to `text-embedding-3-large`)

## Architecture

### Entry Points (3 modes)

| Entry | Framework | Purpose |
|-------|-----------|---------|
| `src/whatever_agent.py` | LangChain CLI | Interactive terminal chat with login/register |
| `src/api.py` | FastAPI | REST API with SSE streaming (`/chat`, `/chat_sync`, `/register`, `/history/{user_id}`) |
| `frontend/` | React (Vite) | Animal Island UI browser frontend |

### Core Agent (`src/whatever_agent.py`)

`RecipeAgent` class wraps a LangChain ReAct agent with LangGraph checkpointing:
- Uses `ChatOpenAI` (compatible with any OpenAI-like API, defaults to DeepSeek Chat)
- System prompt built dynamically from `src/prompt_template.py` + user memory context
- Supports both streaming (`chat_stream`) and synchronous (`chat`) multi-turn conversation
- Agent instance cached per `user_id` in API mode

### Tools (registered with the agent)

1. **`search_recipes(query)`** — Semantic search over local Chroma vector DB (OpenAI embeddings, 1024-dim)
2. **`search_recipes_with_filters(query, difficulty, ingredients)`** — Same but with metadata filters
3. **`web_search(query)`** — DuckDuckGo search + web page content extraction (trafilatura/BeautifulSoup)
4. **`update_memory_as_tool(tastes, dislikes, avoid, difficulty_preference, add_recent_meal)`** — Direct user memory update without LLM call

### Recipe Database (RAG)

- **Source data**: `data/recipes.json` (and versioned variants)
- **Vector store**: Chroma DB persisted in `recipe_db/`
- **Embedding**: `text-embedding-3-large` via OpenAI-compatible API
- **Metadata fields**: `dish_name`, `difficulty_level` (1-5), `key_ingredients` (list)
- **Utilities**:
  - `src/get_embedding.py` — Build vector store from JSON recipes
  - `src/embedding_update.py` — Update individual documents in the vector store

### User Memory System (`src/user_memory.py`)

`UserMemoryManager` stores per-user preferences in SQLite (`user_memory/whatever_to_eat.db`):
- **Preferences**: `tastes`, `dislikes`, `avoid` (allergies), `difficulty_preference`
- **Recent meals**: Timestamped meal history (keeps last 30 entries, shows last 7 in prompt)
- Memory is injected into the system prompt on every turn, and refreshed after each interaction
- Also supports LLM-based extraction via `update_from_conversation()`

### Web Search (`src/web_search_tool.py`)

- DuckDuckGo search via `ddgs` library
- Page content extraction with `trafilatura` (primary) → `BeautifulSoup` (fallback)
- Results capped at 3000 chars per page

### Data Pipeline Files

- `src/generate_description.py` / `src/generate_key_ingredient.py` — Generate recipe descriptions and key ingredients using LLM
- `src/md2json.py` — Convert markdown recipe data to JSON
- `src/utils.py` — Basic OpenAI API wrapper
- `src/langchain_agent.py` — Alternative structured-output agent (Pydantic-based, not actively used)

### API Endpoints (`src/api.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/register` | POST | Register new user |
| `/chat` | POST | Streaming chat (SSE) |
| `/chat_sync` | POST | Non-streaming chat |
| `/history/{user_id}` | GET | Get conversation history |

### Docker

Two services defined in `docker-compose.yml`:
- `api` — FastAPI on port 8000
- `frontend` — React (Vite build) with nginx on port 5173, proxies `/api` to `api`
- `user_memory` mounted as a volume for persistence
- `.env` mounted for configuration

### Frontend (`frontend/`)

Built with **Vite + React + TypeScript** using **animal-island-ui** component library:
- **Login page**: User ID input with register/login
- **Chat page**: SSE streaming chat with Typewriter welcome message
- **Preferences panel**: Modal with tastes, dislikes, allergies, difficulty, recent meals
- **API client**: `src/api/index.ts` — all backend communication, uses `VITE_API_BASE_URL` env var (default `http://localhost:8000`)

Run dev server: `cd frontend && npm run dev` (requires API running on port 8000)
Build: `cd frontend && npx vite build`
