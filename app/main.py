"""FastAPI application entry point for the Memory Narrative Engine.

Routes contain no business logic; they validate input, delegate to the
`NarrativeEngine`, and shape the HTTP response.
"""

import sys

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.engine.narrative_engine import NarrativeEngine
from app.models.event import GameEvent
from app.models.response import HealthStatus, NarrativeResponse, ServiceInfo

logger.remove()
logger.add(sys.stderr, level=settings.log_level)

app = FastAPI(
    title="Memory Narrative Engine",
    description=(
        "A reusable, domain-agnostic backend that generates the next part of "
        "a story for any simulation or game, using Cognee Cloud for "
        "persistent memory and Mistral for story generation."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_engine = NarrativeEngine()


@app.get("/", response_model=ServiceInfo)
async def get_service_info() -> ServiceInfo:
    """Return basic information about this service.

    Returns:
        A `ServiceInfo` describing the engine.
    """

    return ServiceInfo(
        name="Memory Narrative Engine",
        version=app.version,
        description=(
            "Generates the next narrative fragment for any game or simulation "
            "using persistent, session-scoped memory."
        ),
    )


@app.get("/health", response_model=HealthStatus)
async def get_health() -> HealthStatus:
    """Report service health.

    Returns:
        A `HealthStatus` reflecting the current application environment.
    """

    return HealthStatus(status="ok", app_env=settings.app_env)


@app.post("/game/event", response_model=NarrativeResponse)
async def post_game_event(game_event: GameEvent) -> NarrativeResponse:
    """Process a structured game event and return the next story fragment.

    Args:
        game_event: The structured event payload sent by the calling
            simulation/game.

    Returns:
        A `NarrativeResponse` with the generated story and extracted memories.

    Raises:
        HTTPException: If the pipeline fails unexpectedly (status 500).
    """

    try:
        return await _engine.process_event(game_event)
    except Exception as exc:  # noqa: BLE001 - convert any failure into a clean 500
        logger.error(f"Failed to process game event: {exc}")
        raise HTTPException(status_code=500, detail="Failed to generate narrative response.") from exc
