"""Builds the final prompt sent to the story-generation LLM.

Combines the current event, retrieved memories, world state, and
relationship state into a single prompt using the `storyteller.txt`
template. Prompt text is never hardcoded in Python.
"""

import json

from app.config import PROMPTS_DIR, settings
from app.models.event import GameEvent


class ContextBuilder:
    """Assembles LLM prompts from event data, memories, and templates.

    Attributes:
        template: The loaded storyteller prompt template.
    """

    def __init__(self, template_path: str | None = None) -> None:
        """Initialize the context builder by loading the prompt template.

        Args:
            template_path: Optional override path to the storyteller
                template file. Defaults to `prompts/storyteller.txt`.
        """

        path = template_path or str(PROMPTS_DIR / "storyteller.txt")
        with open(path, encoding="utf-8") as file:
            self.template = file.read()

    def build_story_prompt(self, game_event: GameEvent, memories: list[str]) -> str:
        """Build the full user prompt for story generation.

        Args:
            game_event: The incoming structured game event.
            memories: Relevant memories retrieved from Cognee for this session.

        Returns:
            A fully rendered prompt string ready to send to the story
            generation LLM.
        """

        memories_block = "\n".join(f"- {memory}" for memory in memories) if memories else "None yet."
        world_state_block = json.dumps(game_event.world_state, indent=2) if game_event.world_state else "None provided."
        relationships_block = (
            json.dumps(game_event.relationships, indent=2) if game_event.relationships else "None provided."
        )
        event_block = game_event.event.model_dump_json(indent=2, exclude_none=True)

        return self.template.format(
            max_words=settings.story_max_words,
            memories=memories_block,
            world_state=world_state_block,
            relationships=relationships_block,
            event=event_block,
        )

    @staticmethod
    def build_memory_query(game_event: GameEvent) -> str:
        """Build a concise natural-language query used to search memories.

        Args:
            game_event: The incoming structured game event.

        Returns:
            A short string summarizing the event, suitable as a semantic
            search query against stored memories.
        """

        detail = game_event.event
        parts = [detail.actor, detail.action]
        if detail.target:
            parts.append(detail.target)
        if detail.location:
            parts.append(f"at {detail.location}")
        return " ".join(parts)
