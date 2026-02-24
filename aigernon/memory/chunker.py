"""Text chunking utilities for vector memory."""

import re
from dataclasses import dataclass


@dataclass
class Chunk:
    """A chunk of text with metadata."""
    text: str
    index: int
    metadata: dict

    @property
    def token_estimate(self) -> int:
        """Estimate token count (rough: 1 token ~ 4 chars)."""
        return len(self.text) // 4


class TextChunker:
    """
    Text chunker for splitting documents into embeddable chunks.

    Supports multiple chunking strategies optimized for different content types.
    """

    DEFAULT_CHUNK_SIZE = 500  # words
    DEFAULT_OVERLAP = 50  # words

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_OVERLAP,
        min_chunk_size: int = 50,
    ):
        """
        Initialize the chunker.

        Args:
            chunk_size: Target chunk size in words
            overlap: Overlap between chunks in words
            min_chunk_size: Minimum chunk size (smaller chunks are merged)
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.min_chunk_size = min_chunk_size

    def chunk_text(
        self,
        text: str,
        metadata: dict | None = None,
    ) -> list[Chunk]:
        """
        Split text into chunks.

        Args:
            text: Text to chunk
            metadata: Base metadata to include with each chunk

        Returns:
            List of Chunk objects
        """
        if not text or not text.strip():
            return []

        metadata = metadata or {}
        words = text.split()

        if len(words) <= self.chunk_size:
            # Text fits in one chunk
            return [Chunk(text=text.strip(), index=0, metadata=metadata)]

        chunks = []
        start = 0
        chunk_index = 0

        while start < len(words):
            end = min(start + self.chunk_size, len(words))
            chunk_words = words[start:end]
            chunk_text = " ".join(chunk_words)

            chunk_meta = {
                **metadata,
                "chunk_index": chunk_index,
                "chunk_start_word": start,
                "chunk_end_word": end,
            }

            chunks.append(Chunk(
                text=chunk_text,
                index=chunk_index,
                metadata=chunk_meta,
            ))

            # Move start forward, accounting for overlap
            start = end - self.overlap if end < len(words) else end
            chunk_index += 1

        return chunks

    def chunk_markdown(
        self,
        text: str,
        metadata: dict | None = None,
    ) -> list[Chunk]:
        """
        Chunk markdown text, preserving section boundaries.

        Splits on headers when possible, then applies word-based chunking
        to large sections.

        Args:
            text: Markdown text to chunk
            metadata: Base metadata to include with each chunk

        Returns:
            List of Chunk objects
        """
        if not text or not text.strip():
            return []

        metadata = metadata or {}

        # Split on headers (##, ###, etc.)
        sections = self._split_markdown_sections(text)

        chunks = []
        chunk_index = 0

        for section in sections:
            section_text = section["text"].strip()
            if not section_text:
                continue

            section_meta = {
                **metadata,
                "section_header": section.get("header", ""),
                "section_level": section.get("level", 0),
            }

            # If section is small enough, keep as one chunk
            word_count = len(section_text.split())
            if word_count <= self.chunk_size:
                if word_count >= self.min_chunk_size:
                    chunks.append(Chunk(
                        text=section_text,
                        index=chunk_index,
                        metadata={**section_meta, "chunk_index": chunk_index},
                    ))
                    chunk_index += 1
            else:
                # Split large sections
                sub_chunks = self.chunk_text(section_text, section_meta)
                for sub_chunk in sub_chunks:
                    sub_chunk.index = chunk_index
                    sub_chunk.metadata["chunk_index"] = chunk_index
                    chunks.append(sub_chunk)
                    chunk_index += 1

        # Merge small trailing chunks
        chunks = self._merge_small_chunks(chunks)

        return chunks

    def _split_markdown_sections(self, text: str) -> list[dict]:
        """Split markdown into sections by headers."""
        # Pattern matches markdown headers
        header_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)

        sections = []
        last_end = 0
        last_header = ""
        last_level = 0

        for match in header_pattern.finditer(text):
            # Add content before this header
            if last_end < match.start():
                content = text[last_end:match.start()].strip()
                if content:
                    sections.append({
                        "header": last_header,
                        "level": last_level,
                        "text": content,
                    })

            last_header = match.group(2)
            last_level = len(match.group(1))
            last_end = match.end()

        # Add remaining content
        if last_end < len(text):
            content = text[last_end:].strip()
            if content:
                sections.append({
                    "header": last_header,
                    "level": last_level,
                    "text": content,
                })

        # If no sections found, return whole text
        if not sections:
            sections.append({
                "header": "",
                "level": 0,
                "text": text.strip(),
            })

        return sections

    def _merge_small_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        """Merge chunks that are too small."""
        if len(chunks) <= 1:
            return chunks

        merged = []
        buffer_chunk = None

        for chunk in chunks:
            word_count = len(chunk.text.split())

            if buffer_chunk is None:
                if word_count < self.min_chunk_size:
                    buffer_chunk = chunk
                else:
                    merged.append(chunk)
            else:
                # Merge with buffer
                combined_text = buffer_chunk.text + "\n\n" + chunk.text
                combined_words = len(combined_text.split())

                if combined_words <= self.chunk_size:
                    # Keep merging
                    buffer_chunk = Chunk(
                        text=combined_text,
                        index=buffer_chunk.index,
                        metadata=buffer_chunk.metadata,
                    )
                else:
                    # Flush buffer and start new one
                    merged.append(buffer_chunk)
                    if word_count < self.min_chunk_size:
                        buffer_chunk = chunk
                    else:
                        merged.append(chunk)
                        buffer_chunk = None

        # Flush remaining buffer
        if buffer_chunk is not None:
            merged.append(buffer_chunk)

        # Re-index
        for i, chunk in enumerate(merged):
            chunk.index = i
            chunk.metadata["chunk_index"] = i

        return merged

    def chunk_blog_post(
        self,
        content: str,
        title: str = "",
        url: str = "",
        date: str = "",
        tags: list[str] | None = None,
        categories: list[str] | None = None,
    ) -> list[Chunk]:
        """
        Chunk a blog post with rich metadata.

        Args:
            content: Post content (markdown or HTML)
            title: Post title
            url: Post URL
            date: Publication date
            tags: List of tags
            categories: List of categories

        Returns:
            List of Chunk objects with blog metadata
        """
        # Strip HTML if present
        content = self._strip_html(content)

        metadata = {
            "source": "blog",
            "title": title,
            "url": url,
            "date": date,
            "tags": tags or [],
            "categories": categories or [],
        }

        return self.chunk_markdown(content, metadata)

    def _strip_html(self, text: str) -> str:
        """Remove HTML tags from text."""
        # Simple HTML tag removal
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        # Decode common HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&#39;', "'")
        # Clean up whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        return text.strip()
