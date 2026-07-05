"""Extracts deterministic narrative consequences from a generated story using Mistral.

Given the event, relevant memories, prior relationship/world state, and the
newly generated story, this module calculates which NPCs are affected
(including witnesses beyond the direct target), what world-state changes
occurred, which facts should be remembered long-term, and what the player
might plausibly do next.
"""

import json

from loguru import logger

from app.config import PROMPTS_DIR
from app.llm.mistral_service import MistralService
from app.models.event import GameEvent
from app.models.response import NarrativeConsequences

_SYSTEM_PROMPT = (
    "You are a precise game-consequence extraction system. You always respond "
    "with strictly valid JSON and nothing else: no markdown fences, no "
    "commentary. You reason carefully about which characters are affected by "
    "an event, including witnesses, and never invent characters that were not "
    "mentioned in the provided context."
)


class FactExtractor:
    """Extracts structured, deterministic consequences from a story fragment.

    Attributes:
        llm: The `MistralService` used to run extraction.
        template: The loaded consequence-extraction prompt template.
    """

    def __init__(self, llm: MistralService | None = None, template_path: str | None = None) -> None:
        """Initialize the fact extractor.

        Args:
            llm: A `MistralService` instance. A new one is created if omitted.
            template_path: Optional override path to the extractor template
                file. Defaults to `prompts/extractor.txt`.
        """

        self.llm = llm or MistralService()
        path = template_path or str(PROMPTS_DIR / "extractor.txt")
        with open(path, encoding="utf-8") as file:
            self.template = file.read()

    async def extract(
        self,
        game_event: GameEvent,
        story: str,
        memories: list[str],
    ) -> NarrativeConsequences:
        """Extract deterministic narrative consequences from a story fragment.

        Args:
            game_event: The structured event that produced this story,
                including the relationship and world state *before* the event.
            story: The generated narrative text to analyze.
            memories: Relevant memories that were used as context for
                generation, so the extractor can reason consistently with them.

        Returns:
            A `NarrativeConsequences` with relationship updates, world
            updates, new memories, and suggested next actions. Returns an
            empty `NarrativeConsequences` if the LLM response cannot be
            parsed, so extraction failures never break the overall request.
        """

        prompt = self._build_prompt(game_event, story, memories)

        try:
            raw = await self.llm.complete(
                system_prompt=_SYSTEM_PROMPT,
                user_prompt=prompt,
                temperature=0.2,
                max_tokens=700,
            )
        except Exception as exc:  # noqa: BLE001 - extraction is best-effort
            logger.warning(f"Consequence extraction LLM call failed: {exc}")
            return NarrativeConsequences()

        return self._parse(raw)

    def _build_prompt(self, game_event: GameEvent, story: str, memories: list[str]) -> str:
        """Render the extractor prompt template with full event context.

        Args:
            game_event: The structured event that produced the story.
            story: The generated narrative text to analyze.
            memories: Relevant memories used as generation context.

        Returns:
            The fully rendered extraction prompt.
        """

        memories_block = "\n".join(f"- {memory}" for memory in memories) if memories else "None yet."
        relationships_block = (
            json.dumps(game_event.relationships, indent=2) if game_event.relationships else "None provided."
        )
        world_state_block = json.dumps(game_event.world_state, indent=2) if game_event.world_state else "None provided."
        event_block = game_event.event.model_dump_json(indent=2, exclude_none=True)

        return self.template.format(
            event=event_block,
            memories=memories_block,
            relationships=relationships_block,
            world_state=world_state_block,
            story=story,
        )

    @staticmethod
    def _parse(raw: str) -> NarrativeConsequences:
        """Parse the raw LLM output into a `NarrativeConsequences` model.

        Handles the common case where a model wraps JSON in markdown code
        fences despite instructions not to.

        Args:
            raw: The raw text returned by the LLM.

        Returns:
            A `NarrativeConsequences` instance, empty if parsing fails.
        """

        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
            return NarrativeConsequences.model_validate(data)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(f"Failed to parse extracted consequences as JSON: {exc}")
            return NarrativeConsequences()
