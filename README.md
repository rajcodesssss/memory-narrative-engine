# Memory Narrative Engine (MNE)

A reusable, domain-agnostic backend that generates the next part of a story
for any simulation or game. It combines **Cognee Cloud** (persistent,
session-scoped memory) with **Mistral AI** (story generation) behind a
minimal FastAPI service.

The engine is **not** a game — it receives structured game events as JSON
and returns the next part of the story. The game/simulation is built
separately and calls this engine.

## How it works

```
Simulation/Game
     │  POST /game/event
     ▼
NarrativeEngine
     │
     ├─▶ MemoryManager.retrieve()  ──▶ CogneeClient.search()      (Cognee Cloud)
     ├─▶ ContextBuilder.build_story_prompt()   (prompts/storyteller.txt)
     ├─▶ StoryGenerator.generate()             (Mistral)
     ├─▶ FactExtractor.extract()               (Mistral, prompts/extractor.txt)
     └─▶ MemoryManager.store_story() / store_extracted_memories()
              └─▶ CogneeClient.store_memory()  (Cognee Cloud)
     │
     ▼
NarrativeResponse (story, memories_used, extracted_memories, status)
```

## Project structure

```
memory-narrative-engine/
  app/
    main.py                  FastAPI app, routes only
    config.py                Typed settings (pydantic-settings)
    engine/
      narrative_engine.py    Orchestrates the full pipeline
      context_builder.py     Builds LLM prompts from templates
      story_generator.py     Generates story text via Mistral
      fact_extractor.py      Extracts structured facts via Mistral
    memory/
      memory_manager.py      Domain-facing memory API
      cognee_client.py       Sole interface to Cognee Cloud REST API
    llm/
      mistral_service.py     Thin wrapper around the Mistral SDK
    models/
      event.py               Input models (GameEvent)
      response.py             Output models (NarrativeResponse, etc.)
    prompts/
      storyteller.txt        Story generation prompt template
      extractor.txt          Fact extraction prompt template
  pyproject.toml
  .env.example
```

## Setup

Requires Python 3.12+ and [`uv`](https://docs.astral.sh/uv/).

```bash
cd memory-narrative-engine
cp .env.example .env
# edit .env and add your MISTRAL_API_KEY and COGNEE_API_KEY

uv sync
uv run uvicorn app.main:app --reload --port 8000
```

## Environment variables

| Variable                  | Description                                   | Default                    |
|---------------------------|------------------------------------------------|-----------------------------|
| `MISTRAL_API_KEY`         | Mistral AI API key                             | *(required)*                |
| `MISTRAL_MODEL`           | Mistral model used for generation              | `mistral-large-latest`      |
| `COGNEE_API_KEY`          | Cognee Cloud API key                           | *(required)*                |
| `COGNEE_BASE_URL`         | Cognee Cloud API base URL                      | `https://api.cognee.ai`     |
| `COGNEE_DATASET`          | Dataset name prefix used to namespace memories | `memory_narrative_engine`   |
| `APP_ENV`                 | Application environment label                  | `development`                |
| `LOG_LEVEL`               | Loguru log level                               | `INFO`                       |
| `STORY_MAX_WORDS`         | Max words in a generated story                 | `150`                         |
| `MEMORY_RETRIEVAL_LIMIT`  | Max memories retrieved per event               | `8`                            |
| `REQUEST_TIMEOUT_SECONDS` | Timeout for outbound HTTP calls                | `30`                           |

## API

### `GET /`
Returns service metadata.

### `GET /health`
Returns `{"status": "ok", "app_env": "development"}`.

### `POST /game/event`

Request body:

```json
{
  "session_id": "game_001",
  "event": {
    "type": "interaction",
    "actor": "player",
    "action": "help",
    "target": "Emma",
    "location": "Farm"
  },
  "world_state": {
    "day": 5,
    "weather": "Sunny",
    "reputation": 45
  },
  "relationships": {
    "Emma": { "trust": 65, "friendship": 55 }
  }
}
```

Response body:

```json
{
  "story": "...",
  "relationship_updates": [
    {
      "npc": "Emma",
      "trust_delta": 15,
      "friendship_delta": 8,
      "respect_delta": 5,
      "vote_delta": 10,
      "reason": "Player helped repair the farm."
    },
    {
      "npc": "John",
      "trust_delta": 0,
      "friendship_delta": 0,
      "respect_delta": 3,
      "vote_delta": 2,
      "reason": "John witnessed the player's kindness."
    }
  ],
  "world_updates": {
    "reputation_delta": 5,
    "new_events": ["Villagers begin discussing the player's generosity."]
  },
  "new_memories": ["Player helped Emma repair her farm.", "John witnessed the event."],
  "next_actions": ["Talk to Emma", "Visit the Market", "Meet the Village Chief"],
  "status": "success"
}
```

The Narrative Engine returns two things at once: **narrative** (`story`) for the player to read, and **deterministic updates** (`relationship_updates`, `world_updates`) for the simulation to apply immediately — no further interpretation needed on the simulation side. `relationship_updates` covers not just the direct target of the action but any other named NPCs who witnessed it or would plausibly know about it.

## Design notes

- **Domain-agnostic**: `world_state` and `relationships` are free-form
  dictionaries, so the same engine serves fantasy games, detective games,
  village simulators, RPGs, or visual novels without modification.
- **Session-scoped memory**: every memory read/write is namespaced by
  `session_id`, so concurrent game sessions never leak context into each
  other.
- **Graceful degradation**: memory retrieval/storage failures are logged
  and swallowed rather than crashing the request — a fresh session with no
  memories yet still generates a story.
- **No business logic in routes**: `app/main.py` only validates input and
  delegates to `NarrativeEngine`.
- **Prompts are external**: nothing is hardcoded in Python; both prompts
  live in `app/prompts/` as plain text templates.
