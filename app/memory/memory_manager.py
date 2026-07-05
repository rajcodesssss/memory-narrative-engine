"""Domain-facing memory API used by the narrative engine.

`MemoryManager` is the only module the rest of the application should use
to read or write memories. It delegates all actual network I/O to
`CogneeClient`.
"""

from loguru import logger

from app.config import settings
from app.memory.cognee_client import CogneeClient
from app.models.response import NarrativeConsequences


class MemoryManager:
    """Coordinates memory retrieval and persistence for game sessions.

    Attributes:
        client: The underlying `CogneeClient` used for all Cognee I/O.
        retrieval_limit: Default number of memories to fetch per event.
    """

    def __init__(self, client: CogneeClient | None = None, retrieval_limit: int | None = None) -> None:
        """Initialize the memory manager.

        Args:
            client: A `CogneeClient` instance. A new one is created if omitted.
            retrieval_limit: Max memories to retrieve per call. Defaults to
                `settings.memory_retrieval_limit`.
        """

        self.client = client or CogneeClient()
        self.retrieval_limit = retrieval_limit or settings.memory_retrieval_limit

    async def retrieve(self, session_id: str, query: str = "") -> list[str]:
        """Fetch memories relevant to the current event for a session.

        Args:
            session_id: Identifier of the game session to fetch memories for.
            query: Optional natural-language query to focus retrieval (e.g.
                a summary of the current event). Empty string retrieves the
                most relevant recent memories.

        Returns:
            A list of memory text snippets. Returns an empty list if
            retrieval fails, so a fresh session with no memories yet does
            not break story generation.
        """

        try:
            if query:
                return await self.client.search(session_id=session_id, query=query, limit=self.retrieval_limit)
            return await self.client.retrieve_memories(session_id=session_id, limit=self.retrieval_limit)
        except Exception as exc:  # noqa: BLE001 - degrade gracefully, memory is best-effort
            logger.warning(f"Memory retrieval failed for session '{session_id}': {exc}")
            return []

    async def remember(self, session_id: str, text: str) -> None:
        """Store a single piece of text as a memory for a session.

        Args:
            session_id: Identifier of the game session the memory belongs to.
            text: The memory content to persist.
        """

        try:
            await self.client.store_memory(session_id=session_id, text=text)
        except Exception as exc:  # noqa: BLE001 - degrade gracefully, memory is best-effort
            logger.warning(f"Failed to store memory for session '{session_id}': {exc}")

    async def remember_many(self, session_id: str, texts: list[str]) -> None:
        """Store multiple pieces of text as memories in a single round trip.

        Prefer this over calling `remember` in a loop: it batches all texts
        into one `add` + one `cognify` call against Cognee instead of one
        pair per item, which meaningfully cuts latency when a single event
        produces several memories (e.g. relationship updates, world events).

        Args:
            session_id: Identifier of the game session the memories belong to.
            texts: The memory contents to persist. No-ops if empty.
        """

        if not texts:
            return

        try:
            await self.client.store_memories(session_id=session_id, texts=texts)
        except Exception as exc:  # noqa: BLE001 - degrade gracefully, memory is best-effort
            logger.warning(f"Failed to store memories for session '{session_id}': {exc}")

    async def store_story(self, session_id: str, story: str) -> None:
        """Persist a generated story fragment as a memory.

        Args:
            session_id: Identifier of the game session the story belongs to.
            story: The generated narrative text to persist.
        """

        await self.remember(session_id=session_id, text=f"Story event: {story}")

    async def store_consequences(self, session_id: str, consequences: NarrativeConsequences) -> None:
        """Persist all structured consequences derived from a story fragment.

        Each relationship update, world update, and standalone new memory
        is stored as its own memory entry so future semantic searches can
        retrieve them independently and NPC behavior stays consistent with
        what actually happened. All entries are batched into a single
        Cognee round trip rather than stored one at a time.

        Args:
            session_id: Identifier of the game session the facts belong to.
            consequences: The structured consequences extracted from a
                generated story (relationship updates, world updates, new
                memories, and next actions).
        """

        texts: list[str] = []

        for update in consequences.relationship_updates:
            deltas = (
                f"trust {update.trust_delta:+d}, friendship {update.friendship_delta:+d}, "
                f"respect {update.respect_delta:+d}, vote {update.vote_delta:+d}"
            )
            reason = update.reason or "no reason given"
            texts.append(f"Relationship change with {update.npc}: {reason} ({deltas}).")

        world_updates = consequences.world_updates
        if world_updates.reputation_delta != 0:
            texts.append(f"World change: reputation changed by {world_updates.reputation_delta:+d}.")
        for new_event in world_updates.new_events:
            texts.append(f"World event: {new_event}")

        texts.extend(consequences.new_memories)

        await self.remember_many(session_id, texts)