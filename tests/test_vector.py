"""Tests for vector memory module."""

import pytest
import tempfile
from pathlib import Path

from aigernon.memory.chunker import TextChunker, Chunk


class TestTextChunker:
    """Tests for TextChunker."""

    def test_chunk_short_text(self):
        """Short text should stay as single chunk."""
        chunker = TextChunker(chunk_size=100)
        text = "This is a short text that should fit in one chunk."

        chunks = chunker.chunk_text(text)

        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].index == 0

    def test_chunk_long_text(self):
        """Long text should be split into multiple chunks."""
        chunker = TextChunker(chunk_size=10, overlap=2)
        # Create text with 30 words
        words = [f"word{i}" for i in range(30)]
        text = " ".join(words)

        chunks = chunker.chunk_text(text)

        assert len(chunks) > 1
        # First chunk should have chunk_size words
        assert len(chunks[0].text.split()) == 10

    def test_chunk_with_metadata(self):
        """Chunks should include provided metadata."""
        chunker = TextChunker(chunk_size=100)
        text = "Test content"
        metadata = {"source": "test", "author": "tester"}

        chunks = chunker.chunk_text(text, metadata)

        assert len(chunks) == 1
        assert chunks[0].metadata["source"] == "test"
        assert chunks[0].metadata["author"] == "tester"

    def test_chunk_empty_text(self):
        """Empty text should return no chunks."""
        chunker = TextChunker()

        assert chunker.chunk_text("") == []
        assert chunker.chunk_text("   ") == []

    def test_chunk_markdown_sections(self):
        """Markdown should be chunked by sections."""
        chunker = TextChunker(chunk_size=100, min_chunk_size=10)
        text = """# Introduction

This is the intro section with enough words to meet the minimum chunk size requirement for the test.

## First Section

This is the first section content with additional words to ensure it passes the minimum threshold.

## Second Section

This is the second section content with more words to make it a valid chunk for testing purposes.
"""

        chunks = chunker.chunk_markdown(text)

        assert len(chunks) >= 2
        # Check that section headers are captured in metadata
        headers = [c.metadata.get("section_header", "") for c in chunks]
        assert any("Introduction" in h or "First" in h or "Second" in h for h in headers)

    def test_chunk_blog_post(self):
        """Blog post chunking should include rich metadata."""
        chunker = TextChunker(chunk_size=100, min_chunk_size=10)

        chunks = chunker.chunk_blog_post(
            content="This is blog post content with enough words to meet the minimum chunk size requirement for proper testing of the chunking functionality.",
            title="Test Post",
            url="/test-post",
            date="2024-01-01",
            tags=["test", "example"],
            categories=["tech"],
        )

        assert len(chunks) >= 1
        assert chunks[0].metadata["source"] == "blog"
        assert chunks[0].metadata["title"] == "Test Post"
        assert chunks[0].metadata["url"] == "/test-post"

    def test_strip_html(self):
        """HTML should be stripped from content."""
        chunker = TextChunker(min_chunk_size=5)
        html_content = """
        <div>
            <p>Hello <strong>world</strong>! This is a longer paragraph with more content to ensure the chunk meets the minimum size requirement for proper testing of HTML stripping functionality.</p>
            <script>alert('bad');</script>
        </div>
        """

        chunks = chunker.chunk_blog_post(content=html_content, title="Test")

        assert len(chunks) >= 1
        assert "<" not in chunks[0].text
        assert ">" not in chunks[0].text
        assert "alert" not in chunks[0].text

    def test_merge_small_chunks(self):
        """Small chunks should be merged."""
        chunker = TextChunker(chunk_size=50, min_chunk_size=20)
        text = """# Header

Short.

## Another

Also short.

## Yet Another

This one is a bit longer with more content to make it past the minimum."""

        chunks = chunker.chunk_markdown(text)

        # Small chunks should be merged
        for chunk in chunks:
            word_count = len(chunk.text.split())
            # Either meets minimum or is the last chunk
            assert word_count >= 10 or chunk == chunks[-1]


class TestChunk:
    """Tests for Chunk dataclass."""

    def test_token_estimate(self):
        """Token estimate should be roughly 1/4 of character count."""
        chunk = Chunk(
            text="word " * 100,  # 500 chars
            index=0,
            metadata={},
        )

        # ~500 chars / 4 = ~125 tokens
        assert 100 <= chunk.token_estimate <= 150


# Tests that require chromadb (optional)
class TestVectorStore:
    """Tests for VectorStore (requires chromadb)."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for vector store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_import_chromadb(self):
        """ChromaDB should be importable if installed."""
        try:
            import chromadb
            assert chromadb is not None
        except ImportError:
            pytest.skip("chromadb not installed")

    def test_create_vector_store(self, temp_dir):
        """VectorStore should initialize correctly."""
        try:
            from aigernon.memory.vector import VectorStore

            store = VectorStore(persist_directory=temp_dir / "vectordb")
            assert store.persist_directory.exists()

        except ImportError:
            pytest.skip("chromadb not installed")

    def test_add_and_get(self, temp_dir):
        """Documents should be added and retrievable."""
        try:
            from aigernon.memory.vector import VectorStore

            store = VectorStore(persist_directory=temp_dir / "vectordb")

            # Add documents
            ids = store.add(
                collection="test",
                documents=["Hello world", "Goodbye world"],
                metadatas=[{"type": "greeting"}, {"type": "farewell"}],
            )

            assert len(ids) == 2

            # Get documents
            docs = store.get(collection="test", ids=ids)
            assert len(docs) == 2

            # Count
            count = store.count("test")
            assert count == 2

        except ImportError:
            pytest.skip("chromadb not installed")

    def test_upsert(self, temp_dir):
        """Upsert should update existing documents."""
        try:
            from aigernon.memory.vector import VectorStore

            store = VectorStore(persist_directory=temp_dir / "vectordb")

            # Add document
            store.upsert(
                collection="test",
                documents=["Original content"],
                ids=["doc1"],
            )

            # Upsert with same ID
            store.upsert(
                collection="test",
                documents=["Updated content"],
                ids=["doc1"],
            )

            # Should still have only 1 document
            count = store.count("test")
            assert count == 1

            # Content should be updated
            docs = store.get(collection="test", ids=["doc1"])
            assert docs[0]["text"] == "Updated content"

        except ImportError:
            pytest.skip("chromadb not installed")

    def test_delete(self, temp_dir):
        """Documents should be deletable."""
        try:
            from aigernon.memory.vector import VectorStore

            store = VectorStore(persist_directory=temp_dir / "vectordb")

            # Add documents
            store.add(
                collection="test",
                documents=["Doc 1", "Doc 2"],
                ids=["id1", "id2"],
            )

            # Delete one
            store.delete(collection="test", ids=["id1"])

            # Should have 1 left
            count = store.count("test")
            assert count == 1

        except ImportError:
            pytest.skip("chromadb not installed")

    def test_stats(self, temp_dir):
        """Stats should show collection information."""
        try:
            from aigernon.memory.vector import VectorStore

            store = VectorStore(persist_directory=temp_dir / "vectordb")

            # Add to multiple collections
            store.add(collection="col1", documents=["Doc 1"])
            store.add(collection="col2", documents=["Doc 2", "Doc 3"])

            stats = store.get_stats()

            assert "collections" in stats
            assert stats["collections"]["col1"]["count"] == 1
            assert stats["collections"]["col2"]["count"] == 2

        except ImportError:
            pytest.skip("chromadb not installed")


class TestMarkdownImporter:
    """Tests for MarkdownImporter."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_parse_frontmatter(self, temp_dir):
        """Frontmatter should be parsed correctly."""
        # Check chromadb availability first
        try:
            import chromadb
        except ImportError:
            pytest.skip("chromadb not installed")

        from aigernon.memory.vector import VectorStore
        from aigernon.importers.markdown import MarkdownImporter
        from aigernon.memory.chunker import TextChunker

        # Create test file with enough content
        md_file = temp_dir / "test.md"
        md_file.write_text("""---
title: Test Post
date: 2024-01-01
tags:
  - test
  - example
---

# Content

This is the content of the blog post with enough words to meet the minimum chunk size requirement. We need to ensure that there are sufficient words here for the chunker to create at least one valid chunk during the import process.
""")

        store = VectorStore(persist_directory=temp_dir / "vectordb")
        chunker = TextChunker(min_chunk_size=10)
        importer = MarkdownImporter(vector_store=store, chunker=chunker)

        result = importer.import_file(md_file)

        assert result.success
        assert result.documents_processed == 1
        assert result.chunks_created >= 1

    def test_import_directory(self, temp_dir):
        """Directory import should process all files."""
        # Check chromadb availability first
        try:
            import chromadb
        except ImportError:
            pytest.skip("chromadb not installed")

        from aigernon.memory.vector import VectorStore
        from aigernon.importers.markdown import MarkdownImporter
        from aigernon.memory.chunker import TextChunker

        # Create test files with enough content
        content = "This is content with enough words to meet the minimum chunk size requirement for testing purposes."
        (temp_dir / "post1.md").write_text(f"# Post 1\n\n{content}")
        (temp_dir / "post2.md").write_text(f"# Post 2\n\n{content}")
        (temp_dir / "subdir").mkdir()
        (temp_dir / "subdir" / "post3.md").write_text(f"# Post 3\n\n{content}")

        store = VectorStore(persist_directory=temp_dir / "vectordb")
        chunker = TextChunker(min_chunk_size=10)
        importer = MarkdownImporter(vector_store=store, chunker=chunker)

        result = importer.import_all(path=temp_dir)

        assert result.success
        assert result.documents_processed == 3
