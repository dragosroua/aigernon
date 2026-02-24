"""Vector store using ChromaDB for semantic search."""

import json
from pathlib import Path
from typing import Any
from dataclasses import dataclass


@dataclass
class SearchResult:
    """A search result from the vector store."""
    id: str
    text: str
    metadata: dict
    distance: float
    score: float  # 1 - distance (similarity)


class VectorStore:
    """
    Vector store using ChromaDB for semantic search and retrieval.

    Provides collections for different content types:
    - memories: Daily notes, long-term memory
    - blog: Blog posts
    - diary: Personal diary entries
    - coaching: Coaching client data
    - projects: Project notes and tasks
    """

    COLLECTIONS = ["memories", "blog", "diary", "coaching", "projects"]

    def __init__(
        self,
        persist_directory: Path | str,
        embedding_provider: "EmbeddingProvider | None" = None,
    ):
        """
        Initialize the vector store.

        Args:
            persist_directory: Directory to persist ChromaDB data
            embedding_provider: EmbeddingProvider instance for embeddings
        """
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        self._embedding_provider = embedding_provider
        self._client = None
        self._collections: dict[str, Any] = {}

    def _get_client(self):
        """Lazy initialization of ChromaDB client."""
        if self._client is None:
            try:
                import chromadb
                from chromadb.config import Settings
            except ImportError:
                raise ImportError(
                    "chromadb is required for vector memory. "
                    "Install with: pip install aigernon[vector]"
                )

            self._client = chromadb.PersistentClient(
                path=str(self.persist_directory),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True,
                ),
            )
        return self._client

    def _get_embedding_function(self):
        """Get ChromaDB-compatible embedding function."""
        if self._embedding_provider is None:
            return None

        from aigernon.memory.embeddings import ChromaEmbeddingFunction
        return ChromaEmbeddingFunction(self._embedding_provider)

    def _get_collection(self, name: str):
        """Get or create a collection."""
        if name not in self._collections:
            client = self._get_client()
            embedding_fn = self._get_embedding_function()

            self._collections[name] = client.get_or_create_collection(
                name=name,
                embedding_function=embedding_fn,
                metadata={"hnsw:space": "cosine"},
            )

        return self._collections[name]

    def add(
        self,
        collection: str,
        documents: list[str],
        metadatas: list[dict] | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        """
        Add documents to a collection.

        Args:
            collection: Collection name
            documents: List of text documents
            metadatas: Optional list of metadata dicts
            ids: Optional list of document IDs (auto-generated if not provided)

        Returns:
            List of document IDs
        """
        if not documents:
            return []

        col = self._get_collection(collection)

        # Generate IDs if not provided
        if ids is None:
            import hashlib
            import time
            ids = []
            for i, doc in enumerate(documents):
                # Create deterministic ID from content hash + timestamp
                content_hash = hashlib.sha256(doc.encode()).hexdigest()[:12]
                ids.append(f"{collection}_{content_hash}_{int(time.time() * 1000)}_{i}")

        # Ensure metadatas match documents
        if metadatas is None:
            metadatas = [{} for _ in documents]

        # ChromaDB doesn't like None values or lists in metadata
        clean_metadatas = []
        for meta in metadatas:
            clean_meta = {}
            for k, v in meta.items():
                if v is None:
                    continue
                if isinstance(v, list):
                    clean_meta[k] = json.dumps(v)
                elif isinstance(v, (str, int, float, bool)):
                    clean_meta[k] = v
                else:
                    clean_meta[k] = str(v)
            clean_metadatas.append(clean_meta)

        col.add(
            documents=documents,
            metadatas=clean_metadatas,
            ids=ids,
        )

        return ids

    def upsert(
        self,
        collection: str,
        documents: list[str],
        metadatas: list[dict] | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        """
        Add or update documents in a collection.

        Args:
            collection: Collection name
            documents: List of text documents
            metadatas: Optional list of metadata dicts
            ids: Optional list of document IDs

        Returns:
            List of document IDs
        """
        if not documents:
            return []

        col = self._get_collection(collection)

        # Generate IDs if not provided
        if ids is None:
            import hashlib
            ids = []
            for doc in documents:
                content_hash = hashlib.sha256(doc.encode()).hexdigest()[:16]
                ids.append(f"{collection}_{content_hash}")

        # Ensure metadatas match documents
        if metadatas is None:
            metadatas = [{} for _ in documents]

        # Clean metadatas
        clean_metadatas = []
        for meta in metadatas:
            clean_meta = {}
            for k, v in meta.items():
                if v is None:
                    continue
                if isinstance(v, list):
                    clean_meta[k] = json.dumps(v)
                elif isinstance(v, (str, int, float, bool)):
                    clean_meta[k] = v
                else:
                    clean_meta[k] = str(v)
            clean_metadatas.append(clean_meta)

        col.upsert(
            documents=documents,
            metadatas=clean_metadatas,
            ids=ids,
        )

        return ids

    def search(
        self,
        collection: str,
        query: str,
        n_results: int = 10,
        where: dict | None = None,
        where_document: dict | None = None,
    ) -> list[SearchResult]:
        """
        Search for similar documents.

        Args:
            collection: Collection name
            query: Query text
            n_results: Maximum number of results
            where: Metadata filter (e.g., {"source": "blog"})
            where_document: Document content filter

        Returns:
            List of SearchResult objects
        """
        col = self._get_collection(collection)

        kwargs: dict[str, Any] = {
            "query_texts": [query],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }

        if where:
            kwargs["where"] = where
        if where_document:
            kwargs["where_document"] = where_document

        results = col.query(**kwargs)

        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results["distances"] else 0
                search_results.append(SearchResult(
                    id=doc_id,
                    text=results["documents"][0][i] if results["documents"] else "",
                    metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                    distance=distance,
                    score=1 - distance,  # Convert distance to similarity
                ))

        return search_results

    def get(
        self,
        collection: str,
        ids: list[str] | None = None,
        where: dict | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        """
        Get documents by ID or filter.

        Args:
            collection: Collection name
            ids: Optional list of document IDs
            where: Optional metadata filter
            limit: Maximum number of results

        Returns:
            List of document dicts with id, text, metadata
        """
        col = self._get_collection(collection)

        kwargs: dict[str, Any] = {
            "include": ["documents", "metadatas"],
        }

        if ids:
            kwargs["ids"] = ids
        if where:
            kwargs["where"] = where
        if limit:
            kwargs["limit"] = limit

        results = col.get(**kwargs)

        docs = []
        if results["ids"]:
            for i, doc_id in enumerate(results["ids"]):
                docs.append({
                    "id": doc_id,
                    "text": results["documents"][i] if results["documents"] else "",
                    "metadata": results["metadatas"][i] if results["metadatas"] else {},
                })

        return docs

    def delete(
        self,
        collection: str,
        ids: list[str] | None = None,
        where: dict | None = None,
    ) -> None:
        """
        Delete documents by ID or filter.

        Args:
            collection: Collection name
            ids: Optional list of document IDs to delete
            where: Optional metadata filter for deletion
        """
        col = self._get_collection(collection)

        if ids:
            col.delete(ids=ids)
        elif where:
            col.delete(where=where)

    def count(self, collection: str) -> int:
        """
        Get the number of documents in a collection.

        Args:
            collection: Collection name

        Returns:
            Document count
        """
        col = self._get_collection(collection)
        return col.count()

    def list_collections(self) -> list[str]:
        """
        List all collections.

        Returns:
            List of collection names
        """
        client = self._get_client()
        return [col.name for col in client.list_collections()]

    def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about the vector store.

        Returns:
            Dict with collection stats
        """
        client = self._get_client()
        stats = {
            "persist_directory": str(self.persist_directory),
            "collections": {},
        }

        for col in client.list_collections():
            stats["collections"][col.name] = {
                "count": col.count(),
            }

        return stats

    def reset(self) -> None:
        """
        Reset the entire vector store (delete all data).

        WARNING: This deletes all collections and documents!
        """
        client = self._get_client()
        client.reset()
        self._collections = {}

    def delete_collection(self, name: str) -> None:
        """
        Delete a collection.

        Args:
            name: Collection name to delete
        """
        client = self._get_client()
        try:
            client.delete_collection(name)
            if name in self._collections:
                del self._collections[name]
        except ValueError:
            pass  # Collection doesn't exist


# Convenience function for creating a configured VectorStore
def create_vector_store(
    data_dir: Path | str,
    api_key: str | None = None,
    api_base: str | None = None,
    embedding_model: str = "text-embedding-3-small",
) -> VectorStore:
    """
    Create a configured VectorStore instance.

    Args:
        data_dir: Base data directory (vectordb will be created inside)
        api_key: API key for embeddings
        api_base: API base URL for embeddings
        embedding_model: Embedding model to use

    Returns:
        Configured VectorStore instance
    """
    from aigernon.memory.embeddings import EmbeddingProvider

    persist_dir = Path(data_dir) / "vectordb"

    provider = EmbeddingProvider(
        model=embedding_model,
        api_key=api_key,
        api_base=api_base,
    )

    return VectorStore(
        persist_directory=persist_dir,
        embedding_provider=provider,
    )
