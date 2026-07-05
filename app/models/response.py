"""Output data models returned by the narrative engine."""

from typing import Literal

from pydantic import BaseModel, Field


class RelationshipUpdate(BaseModel):
    """A deterministic relationship change the simulation should apply to one NPC.

    Only the delta fields that are actually relevant to the event should be
    non-zero; fields the narrative engine has no opinion on default to 0 so
    the simulation can apply every update uniformly without special-casing
    missing fields.

    Attributes:
        npc: Name of the affected NPC (may be the direct target or a witness).
        trust_delta: Change in trust, positive or negative.
        friendship_delta: Change in friendship, positive or negative.
        respect_delta: Change in respect, positive or negative.
        vote_delta: Change in political/voting support, positive or negative.
        reason: Short, human-readable explanation of why this update occurred.
    """

    npc: str
    trust_delta: int = 0
    friendship_delta: int = 0
    respect_delta: int = 0
    vote_delta: int = 0
    reason: str = ""


class WorldUpdates(BaseModel):
    """Deterministic world-state changes the simulation should apply.

    Attributes:
        reputation_delta: Change to the player's overall reputation.
        new_events: Short descriptions of new world events triggered by
            this story beat (e.g. rumors spreading, weather shifting).
    """

    reputation_delta: int = 0
    new_events: list[str] = Field(default_factory=list)


class NarrativeConsequences(BaseModel):
    """Structured consequences derived from a generated story fragment.

    This is the internal handoff between `FactExtractor` and
    `NarrativeEngine`: everything needed to both persist memories and
    populate the final `NarrativeResponse`.

    Attributes:
        relationship_updates: Deterministic relationship deltas per NPC,
            including witnesses beyond the direct target of the action.
        world_updates: Deterministic world-state deltas and new events.
        new_memories: Standalone facts worth persisting for future recall.
        next_actions: Short, player-facing suggestions for what to do next.
    """

    relationship_updates: list[RelationshipUpdate] = Field(default_factory=list)
    world_updates: WorldUpdates = Field(default_factory=WorldUpdates)
    new_memories: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class NarrativeResponse(BaseModel):
    """Response returned to the calling simulation/game.

    Attributes:
        story: The generated next part of the story, for display to the player.
        relationship_updates: Deterministic relationship deltas the
            simulation should apply immediately, one entry per affected NPC.
        world_updates: Deterministic world-state deltas the simulation
            should apply immediately.
        new_memories: Standalone facts extracted from this event, already
            persisted back into Cognee for future recall.
        next_actions: Short, player-facing suggestions for what to do next.
        status: Outcome of the request.
    """

    story: str
    relationship_updates: list[RelationshipUpdate] = Field(default_factory=list)
    world_updates: WorldUpdates = Field(default_factory=WorldUpdates)
    new_memories: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    status: Literal["success", "error"] = "success"


class ServiceInfo(BaseModel):
    """Basic service metadata returned by the root endpoint."""

    name: str
    version: str
    description: str


class HealthStatus(BaseModel):
    """Health check response."""

    status: Literal["ok", "degraded"]
    app_env: str



class ServiceInfo(BaseModel):
    """Basic service metadata returned by the root endpoint."""

    name: str
    version: str
    description: str


class HealthStatus(BaseModel):
    """Health check response."""

    status: Literal["ok", "degraded"]
    app_env: str
