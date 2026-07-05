"""Orchestrates the full narrative generation pipeline.

This is the only entry point FastAPI routes should call. All business
logic (memory retrieval, prompt construction, generation, extraction,
and persistence) lives here and in the classes it composes, never in the
API layer.
"""

from loguru import logger

from app.engine.context_builder import ContextBuilder
from app.engine.fact_extractor import FactExtractor
from app.engine.story_generator import StoryGenerator
from app.memory.memory_manager import MemoryManager
from app.models.event import GameEvent
from app.models.response import NarrativeResponse


class NarrativeEngine:
    """Coordinates memory, context building, generation, and extraction.

    Attributes:
        memory: Manages retrieval and persistence of session memories.
        context_builder: Builds LLM prompts from event and memory data.
        story_generator: Generates the next story fragment.
        fact_extractor: Extracts structured facts from generated stories.
    """

    def __init__(
        self,
        memory: MemoryManager | None = None,
        context_builder: ContextBuilder | None = None,
        story_generator: StoryGenerator | None = None,
        fact_extractor: FactExtractor | None = None,
    ) -> None:
        """Initialize the narrative engine and its collaborators.

        Args:
            memory: A `MemoryManager` instance. A new one is created if omitted.
            context_builder: A `ContextBuilder` instance. A new one is
                created if omitted.
            story_generator: A `StoryGenerator` instance. A new one is
                created if omitted.
            fact_extractor: A `FactExtractor` instance. A new one is
                created if omitted.
        """

        self.memory = memory or MemoryManager()
        self.context_builder = context_builder or ContextBuilder()
        self.story_generator = story_generator or StoryGenerator()
        self.fact_extractor = fact_extractor or FactExtractor()

    async def process_event(self, game_event: GameEvent) -> NarrativeResponse:
        """Run the full event -> story -> consequences -> memory pipeline.

        Flow:
            1. Retrieve relevant memories from Cognee for this session.
            2. Use the relationship and world state already provided on the
               event (sent by the simulation) alongside those memories to
               build a story-generation prompt.
            3. Generate the next narrative fragment with Mistral.
            4. Calculate deterministic narrative consequences: relationship
               updates (including witnesses beyond the direct target),
               world updates, new long-term memories, and suggested next
               actions.
            5. Persist the story and extracted consequences back into Cognee.
            6. Return the story plus structured updates for the simulation
               to apply immediately.

        Args:
            game_event: The structured event received from the simulation/game.

        Returns:
            A `NarrativeResponse` containing the generated story,
            relationship updates, world updates, new memories, suggested
            next actions, and the request status.
        """

        logger.info(f"Processing event for session '{game_event.session_id}': {game_event.event.action}")

        memory_query = self.context_builder.build_memory_query(game_event)
        memories = await self.memory.retrieve(session_id=game_event.session_id, query=memory_query)

        prompt = self.context_builder.build_story_prompt(game_event, memories)
        story = await self.story_generator.generate(prompt)

        consequences = await self.fact_extractor.extract(game_event=game_event, story=story, memories=memories)

        await self.memory.store_story(session_id=game_event.session_id, story=story)
        await self.memory.store_consequences(session_id=game_event.session_id, consequences=consequences)

        logger.info(f"Completed event for session '{game_event.session_id}'.")

        return NarrativeResponse(
            story=story,
            relationship_updates=consequences.relationship_updates,
            world_updates=consequences.world_updates,
            new_memories=consequences.new_memories,
            next_actions=consequences.next_actions,
            status="success",
        )
