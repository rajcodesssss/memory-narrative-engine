"""Generates the next narrative fragment using Mistral."""

from app.config import settings
from app.llm.mistral_service import MistralService

_SYSTEM_PROMPT = (
    "You are a masterful, genre-agnostic narrative engine embedded inside a game "
    "backend. You write only immersive story prose, never JSON, lists, or "
    "commentary. You strictly respect any word limit given to you."
)


class StoryGenerator:
    """Produces the next part of a story from a fully-built prompt.

    Attributes:
        llm: The `MistralService` used to generate text.
    """

    def __init__(self, llm: MistralService | None = None) -> None:
        """Initialize the story generator.

        Args:
            llm: A `MistralService` instance. A new one is created if omitted.
        """

        self.llm = llm or MistralService()

    async def generate(self, prompt: str) -> str:
        """Generate the next narrative fragment.

        Args:
            prompt: The fully-rendered story prompt from `ContextBuilder`.

        Returns:
            The generated story text, limited to approximately
            `settings.story_max_words` words.
        """

        story = await self.llm.complete(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=prompt,
            temperature=0.8,
            max_tokens=400,
        )
        return self._enforce_word_limit(story, settings.story_max_words)

    @staticmethod
    def _enforce_word_limit(text: str, max_words: int) -> str:
        """Trim generated text to a maximum word count as a safety net.

        Args:
            text: The raw generated story text.
            max_words: The maximum number of words to allow.

        Returns:
            The text, truncated to `max_words` words if it exceeded the limit.
        """

        words = text.split()
        if len(words) <= max_words:
            return text
        return " ".join(words[:max_words]).rstrip(",;:") + "..."
