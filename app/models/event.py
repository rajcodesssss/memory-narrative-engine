"""Input data models for incoming game/simulation events.

These models are intentionally domain-agnostic: they use free-form
dictionaries for world state and relationship data so the engine can serve
fantasy games, detective games, village simulators, RPGs, visual novels, or
any other simulation without modification.
"""

from typing import Any

from pydantic import BaseModel, Field


class GameEventDetail(BaseModel):
    """Describes a single atomic event that occurred in the simulation.

    Attributes:
        type: Category of the event (e.g. "interaction", "discovery", "combat").
        actor: The entity that initiated the event (e.g. "player").
        action: The action performed (e.g. "help", "attack", "investigate").
        target: The entity or object the action was directed at, if any.
        location: Where the event took place, if relevant.
        metadata: Any additional free-form data describing the event.
    """

    type: str = Field(..., description="Category of the event.")
    actor: str = Field(..., description="Entity that initiated the event.")
    action: str = Field(..., description="Action performed by the actor.")
    target: str | None = Field(default=None, description="Target of the action.")
    location: str | None = Field(default=None, description="Location of the event.")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Any additional free-form event data.",
    )


class GameEvent(BaseModel):
    """Top-level payload sent by a simulation/game to the narrative engine.

    Attributes:
        session_id: Unique identifier for the ongoing game session. Used to
            scope memory storage and retrieval so unrelated sessions never
            leak into each other's context.
        event: The structured event that just occurred.
        world_state: Free-form key/value snapshot of the current world
            (e.g. day count, weather, reputation).
        relationships: Free-form mapping of entity name to relationship
            attributes (e.g. trust, friendship scores).
    """

    session_id: str = Field(..., description="Unique identifier for the game session.")
    event: GameEventDetail = Field(..., description="The event that just occurred.")
    world_state: dict[str, Any] = Field(
        default_factory=dict,
        description="Free-form snapshot of the current world state.",
    )
    relationships: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Free-form relationship state keyed by entity name.",
    )
