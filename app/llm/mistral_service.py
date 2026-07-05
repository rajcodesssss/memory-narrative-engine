"""Thin async wrapper around the Mistral AI chat completion API."""

from mistralai.client import Mistral

from app.config import settings


class MistralServiceError(RuntimeError):
    """Raised when a Mistral API call fails."""


class MistralService:
    """Wraps the Mistral SDK for text generation.

    Attributes:
        model: The Mistral model identifier used for completions.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        """Initialize the Mistral service.

        Args:
            api_key: Mistral API key. Defaults to `settings.mistral_api_key`.
            model: Mistral model name. Defaults to `settings.mistral_model`.
        """

        self._client = Mistral(api_key=api_key or settings.mistral_api_key)
        self.model = model or settings.mistral_model

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 600,
    ) -> str:
        """Generate a chat completion from Mistral.

        Args:
            system_prompt: Instructions establishing the model's role/behavior.
            user_prompt: The fully-built prompt content for this request.
            temperature: Sampling temperature; higher is more creative.
            max_tokens: Maximum number of tokens to generate.

        Returns:
            The generated text content, stripped of leading/trailing whitespace.

        Raises:
            MistralServiceError: If the API call fails or returns no content.
        """

        try:
            response = await self._client.chat.complete_async(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:  # noqa: BLE001 - surface as a domain-specific error
            raise MistralServiceError(f"Mistral completion request failed: {exc}") from exc

        if not response.choices:
            raise MistralServiceError("Mistral returned no completion choices.")

        content = response.choices[0].message.content
        if not content or not isinstance(content, str):
            raise MistralServiceError("Mistral returned an empty completion.")

        return content.strip()
