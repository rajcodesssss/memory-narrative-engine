"""Thin async client for the Cognee Cloud REST API.

This is the ONLY module in the application permitted to communicate
directly with Cognee. All other code must go through `MemoryManager`.
"""

from typing import Any

import httpx
from loguru import logger

from app.config import settings


class CogneeClientError(RuntimeError):
    """Raised when a Cognee Cloud API call fails."""


class CogneeClient:
    """Async wrapper around the Cognee Cloud REST API.

    Attributes:
        base_url: Root URL of the Cognee Cloud API.
        dataset: Dataset name used to namespace stored memories.
        timeout: Timeout, in seconds, applied to all HTTP requests.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        dataset: str | None = None,
        timeout: int | None = None,
    ) -> None:
        """Initialize the Cognee client.

        Args:
            api_key: Cognee Cloud API key. Defaults to `settings.cognee_api_key`.
            base_url: Base URL of the Cognee Cloud API. Defaults to
                `settings.cognee_base_url`.
            dataset: Dataset name used to namespace memories. Defaults to
                `settings.cognee_dataset`.
            timeout: Request timeout in seconds. Defaults to
                `settings.request_timeout_seconds`.
        """

        self._api_key = api_key or settings.cognee_api_key
        self.base_url = (base_url or settings.cognee_base_url).rstrip("/")
        self.dataset = dataset or settings.cognee_dataset
        self.timeout = timeout or settings.request_timeout_seconds

    def _auth_headers(self) -> dict[str, str]:
        """Build the authorization header for Cognee Cloud requests.

        Note: only the API key header is set here. Content-Type is
        deliberately NOT included — httpx sets the correct Content-Type
        automatically based on whether a request is sent as JSON (`json=`)
        or multipart form data (`files=`/`data=`), and manually forcing
        `application/json` breaks the multipart `/add` endpoint.

        Returns:
            A dictionary containing the `X-Api-Key` header.
        """

        return {"X-Api-Key": self._api_key}

    async def store_memory(self, session_id: str, text: str) -> dict[str, Any]:
        """Persist a single piece of text as a memory in Cognee Cloud.

        Convenience wrapper around `store_memories` for the common case of
        storing one memory at a time.

        Args:
            session_id: Identifier used to namespace memories per game session.
            text: The memory content to store.

        Returns:
            The parsed JSON response body from Cognee Cloud's cognify call.

        Raises:
            CogneeClientError: If either the add or cognify request fails,
                or Cognee returns a non-success status code.
        """

        return await self.store_memories(session_id=session_id, texts=[text])

    async def store_memories(
        self, session_id: str, texts: list[str], run_cognify_in_background: bool = True
    ) -> dict[str, Any]:
        """Persist multiple pieces of text as memories in a single round trip.

        Batches all texts into one `/api/v1/add` call (multiple file parts
        under the same `data` field) followed by one `/api/v1/cognify` call,
        instead of one add+cognify pair per text. This matters because
        cognify can take several seconds even for small inputs, and a single
        game event can otherwise trigger many sequential round trips (one
        per relationship update, world event, etc.).

        Cognee's `/api/v1/add` endpoint requires `multipart/form-data`
        (not JSON), with the dataset name passed as `datasetName`, and each
        item in `data` must be sent as an actual file part (with a filename)
        rather than a bare form field, or Cognee rejects it with "Expected
        UploadFile, received: str".

        Args:
            session_id: Identifier used to namespace memories per game session.
            texts: The memory contents to store. No-ops if empty.
            run_cognify_in_background: If True (default), cognify runs
                asynchronously on Cognee's side and this call returns as
                soon as it's queued — memories become searchable a few
                seconds later rather than blocking the caller. Set False to
                block until cognify completes and guarantee the data is
                immediately searchable afterward.

        Returns:
            The parsed JSON response body from Cognee Cloud's cognify call.
            Returns an empty dict if `texts` is empty.

        Raises:
            CogneeClientError: If either the add or cognify request fails,
                or Cognee returns a non-success status code.
        """

        if not texts:
            return {}

        dataset_name = f"{self.dataset}_{session_id}"
        file_parts = [
            ("data", (f"memory_{i}.txt", text.encode("utf-8"), "text/plain"))
            for i, text in enumerate(texts)
        ]

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/add",
                    headers=self._auth_headers(),
                    data={"datasetName": dataset_name},
                    files=file_parts,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    f"Cognee store_memories (add) failed: {exc} | response body: {exc.response.text}"
                )
                raise CogneeClientError(f"Failed to store memories in Cognee: {exc}") from exc
            except httpx.HTTPError as exc:
                logger.error(f"Cognee store_memories (add) failed: {exc}")
                raise CogneeClientError(f"Failed to store memories in Cognee: {exc}") from exc

        return await self.cognify(session_id, run_in_background=run_cognify_in_background)

    async def cognify(self, session_id: str, run_in_background: bool = True) -> dict[str, Any]:
        """Process a session's dataset into a searchable knowledge graph.

        Must be called after `store_memory`/`store_memories`/`add` and
        before `search` will return any results for the dataset — Cognee
        only indexes data that has been cognified.

        Args:
            session_id: Identifier used to namespace memories per game session.
            run_in_background: If True (default), returns as soon as the
                cognify job is queued instead of waiting for it to finish.
                Note that data won't actually be searchable until the
                background job completes on Cognee's side, so a search
                immediately after may still miss very recent memories.

        Returns:
            The parsed JSON response body from Cognee Cloud.

        Raises:
            CogneeClientError: If the request fails or Cognee returns a
                non-success status code.
        """

        dataset_name = f"{self.dataset}_{session_id}"
        payload = {"datasets": [dataset_name], "run_in_background": run_in_background}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/cognify",
                    headers=self._auth_headers(),
                    json=payload,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    f"Cognee cognify failed: {exc} | response body: {exc.response.text}"
                )
                raise CogneeClientError(f"Failed to cognify Cognee dataset: {exc}") from exc
            except httpx.HTTPError as exc:
                logger.error(f"Cognee cognify failed: {exc}")
                raise CogneeClientError(f"Failed to cognify Cognee dataset: {exc}") from exc

        return response.json()

    async def retrieve_memories(self, session_id: str, limit: int) -> list[str]:
        """Retrieve the most recent memories for a session, unfiltered by query.

        Args:
            session_id: Identifier used to namespace memories per game session.
            limit: Maximum number of memories to return.

        Returns:
            A list of memory text snippets, most relevant first.

        Raises:
            CogneeClientError: If the request fails or Cognee returns a
                non-success status code.
        """

        return await self.search(session_id=session_id, query="", limit=limit)

    async def search(self, session_id: str, query: str, limit: int) -> list[str]:
        """Search stored memories for a session using Cognee's semantic search.

        Cognee's `/api/v1/search` endpoint takes JSON with `query` (not
        `search_query`) and scopes to a dataset via the `datasets` list
        field (not a single `dataset_name` string).

        Args:
            session_id: Identifier used to namespace memories per session.
            query: Natural language search query. An empty string requests
                the most relevant/recent memories without a specific filter.
            limit: Maximum number of memory snippets to return.

        Returns:
            A list of memory text snippets returned by Cognee, most
            relevant first.

        Raises:
            CogneeClientError: If the request fails or Cognee returns a
                non-success status code.
        """

        payload = {
            "query": query or "recent important events and relationships",
            "search_type": "GRAPH_COMPLETION",
            "datasets": [f"{self.dataset}_{session_id}"],
            "top_k": limit,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/search",
                    headers=self._auth_headers(),
                    json=payload,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    f"Cognee search failed: {exc} | response body: {exc.response.text}"
                )
                raise CogneeClientError(f"Failed to search Cognee memories: {exc}") from exc
            except httpx.HTTPError as exc:
                logger.error(f"Cognee search failed: {exc}")
                raise CogneeClientError(f"Failed to search Cognee memories: {exc}") from exc

        body = response.json()
        return self._extract_memory_texts(body, limit)

    @staticmethod
    def _extract_memory_texts(body: Any, limit: int) -> list[str]:
        """Normalize Cognee's search response into a flat list of strings.

        Cognee Cloud may return results as a list of strings, a list of
        dicts with a "text" field, or a dict with a "results" key. This
        helper defensively handles each shape.

        Args:
            body: Raw JSON-decoded response body from Cognee.
            limit: Maximum number of items to return.

        Returns:
            A list of plain-text memory snippets.
        """

        results: list[Any]
        if isinstance(body, list):
            results = body
        elif isinstance(body, dict):
            results = body.get("results") or body.get("data") or []
        else:
            results = []

        texts: list[str] = []
        for item in results[:limit]:
            if isinstance(item, str):
                texts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content") or item.get("answer")
                if text:
                    texts.append(str(text))

        return texts