"""Base importer class for content import."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from aigernon.memory.vector import VectorStore
from aigernon.memory.chunker import TextChunker


@dataclass
class ImportResult:
    """Result of an import operation."""
    success: bool
    documents_processed: int = 0
    chunks_created: int = 0
    errors: list[str] = field(default_factory=list)
    skipped: int = 0

    def __str__(self) -> str:
        status = "Success" if self.success else "Failed"
        return (
            f"{status}: {self.documents_processed} documents, "
            f"{self.chunks_created} chunks, {len(self.errors)} errors, "
            f"{self.skipped} skipped"
        )


class BaseImporter(ABC):
    """
    Base class for content importers.

    Importers load content from various sources (files, APIs, etc.)
    and index them into the vector store.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        collection: str,
        chunker: TextChunker | None = None,
        on_progress: Callable[[int, int, str], None] | None = None,
    ):
        """
        Initialize the importer.

        Args:
            vector_store: VectorStore to import into
            collection: Collection name to use
            chunker: TextChunker instance (uses defaults if not provided)
            on_progress: Optional callback for progress updates (current, total, message)
        """
        self.vector_store = vector_store
        self.collection = collection
        self.chunker = chunker or TextChunker()
        self.on_progress = on_progress

    def _report_progress(self, current: int, total: int, message: str) -> None:
        """Report progress if callback is set."""
        if self.on_progress:
            self.on_progress(current, total, message)

    @abstractmethod
    def import_all(self, **kwargs) -> ImportResult:
        """
        Import all content from the source.

        Returns:
            ImportResult with statistics
        """
        pass

    def _index_chunks(
        self,
        chunks: list[Any],
        base_id: str | None = None,
    ) -> int:
        """
        Index chunks into the vector store.

        Args:
            chunks: List of Chunk objects
            base_id: Optional base ID for generating chunk IDs

        Returns:
            Number of chunks indexed
        """
        if not chunks:
            return 0

        documents = [chunk.text for chunk in chunks]
        metadatas = [chunk.metadata for chunk in chunks]

        # Generate IDs if base_id provided
        ids = None
        if base_id:
            ids = [f"{base_id}_chunk_{chunk.index}" for chunk in chunks]

        self.vector_store.add(
            collection=self.collection,
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )

        return len(chunks)
