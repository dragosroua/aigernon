"""Embedding provider using LiteLLM for OpenAI-compatible embeddings."""

import asyncio
from typing import Any


class EmbeddingProvider:
    """
    Embedding provider that uses LiteLLM for OpenAI-compatible embeddings.

    Supports OpenAI, OpenRouter, and any OpenAI-compatible API.
    """

    DEFAULT_MODEL = "text-embedding-3-small"
    DEFAULT_DIMENSIONS = 1536

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        api_base: str | None = None,
        dimensions: int = DEFAULT_DIMENSIONS,
    ):
        """
        Initialize the embedding provider.

        Args:
            model: Embedding model name (default: text-embedding-3-small)
            api_key: API key for the provider
            api_base: API base URL (for OpenRouter or custom endpoints)
            dimensions: Embedding dimensions (default: 1536)
        """
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self.dimensions = dimensions
        self._litellm = None

    def _get_litellm(self):
        """Lazy import litellm."""
        if self._litellm is None:
            import litellm
            self._litellm = litellm
        return self._litellm

    def embed(self, texts: str | list[str]) -> list[list[float]]:
        """
        Generate embeddings for text(s).

        Args:
            texts: Single text or list of texts to embed

        Returns:
            List of embedding vectors
        """
        if isinstance(texts, str):
            texts = [texts]

        if not texts:
            return []

        litellm = self._get_litellm()

        # Build kwargs
        kwargs: dict[str, Any] = {
            "model": self.model,
            "input": texts,
        }

        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base

        # Some models support dimensions parameter
        if "text-embedding-3" in self.model:
            kwargs["dimensions"] = self.dimensions

        response = litellm.embedding(**kwargs)

        # Extract embeddings from response
        embeddings = [item["embedding"] for item in response.data]
        return embeddings

    async def aembed(self, texts: str | list[str]) -> list[list[float]]:
        """
        Async version of embed.

        Args:
            texts: Single text or list of texts to embed

        Returns:
            List of embedding vectors
        """
        # Run sync embed in thread pool
        return await asyncio.to_thread(self.embed, texts)

    def embed_query(self, text: str) -> list[float]:
        """
        Embed a single query text.

        Args:
            text: Query text to embed

        Returns:
            Embedding vector
        """
        embeddings = self.embed(text)
        return embeddings[0] if embeddings else []

    async def aembed_query(self, text: str) -> list[float]:
        """
        Async version of embed_query.

        Args:
            text: Query text to embed

        Returns:
            Embedding vector
        """
        return await asyncio.to_thread(self.embed_query, text)


class ChromaEmbeddingFunction:
    """
    ChromaDB-compatible embedding function wrapper.

    This wraps EmbeddingProvider to work with ChromaDB's embedding_function interface.
    """

    def __init__(self, provider: EmbeddingProvider):
        """
        Initialize with an EmbeddingProvider.

        Args:
            provider: The embedding provider to wrap
        """
        self.provider = provider

    def __call__(self, input: list[str]) -> list[list[float]]:
        """
        Generate embeddings (ChromaDB interface).

        Args:
            input: List of texts to embed

        Returns:
            List of embedding vectors
        """
        return self.provider.embed(input)
