# Telegram Bot (Phase 2)

The bot is **not yet implemented** but the architecture is locked in:

```
[ Telegram ] → [ bot/main.py ] → [ FastAPI /api ] → [ DuckDB ]
                       ↓
                  [ LLM (GPT-4o / Gemini) ] for NL → query routing
```

## How it will work

1. The user sends a message in Telegram (command or natural language).
2. `bot/main.py` (python-telegram-bot) classifies intent:
   - **Slash commands** (`/trend Maruti Apr 2026`, `/top States`, `/export`) map directly to API calls.
   - **Free text** ("compare Tata vs Mahindra Q1 2026") goes to the LLM with a strict system prompt that emits a JSON tool call like `{"endpoint": "/pivot", "params": {...}}`.
3. The bot calls the corresponding FastAPI endpoint, formats the result as a markdown table, and (optionally) attaches a Plotly chart rendered to PNG.
4. Hard guardrail in the system prompt: the LLM may **only** call whitelisted endpoints. Anything off-topic returns `"I can only answer questions about Vahan registration data."`

## Implementation checklist

- [ ] `pip install python-telegram-bot openai` (or `google-generativeai`)
- [ ] Add `BOT_TOKEN` and `OPENAI_API_KEY` to environment
- [ ] Implement `bot/handlers.py` with `/start`, `/trend`, `/top`, `/export`, free-text
- [ ] Implement `bot/router.py` that converts LLM JSON → API call → markdown reply
- [ ] Add `Procfile` / Render service so the bot runs alongside the API

The query layer in `core/queries.py` is already designed to be the single source of truth — the bot will not duplicate any business logic.
