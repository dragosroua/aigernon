"""Markdown folder importer."""

import re
from pathlib import Path
from typing import Callable

from aigernon.importers.base import BaseImporter, ImportResult
from aigernon.memory.vector import VectorStore
from aigernon.memory.chunker import TextChunker


class MarkdownImporter(BaseImporter):
    """
    Import markdown files from a directory into vector memory.

    Supports:
    - Recursive directory scanning
    - Frontmatter parsing (YAML)
    - Various markdown flavors
    """

    def __init__(
        self,
        vector_store: VectorStore,
        collection: str = "blog",
        chunker: TextChunker | None = None,
        on_progress: Callable[[int, int, str], None] | None = None,
    ):
        super().__init__(vector_store, collection, chunker, on_progress)

    def import_all(
        self,
        path: Path | str,
        pattern: str = "**/*.md",
        exclude_patterns: list[str] | None = None,
    ) -> ImportResult:
        """
        Import all markdown files from a directory.

        Args:
            path: Directory path to scan
            pattern: Glob pattern for finding files (default: **/*.md)
            exclude_patterns: List of patterns to exclude (e.g., ["**/node_modules/**"])

        Returns:
            ImportResult with statistics
        """
        path = Path(path)
        if not path.exists():
            return ImportResult(
                success=False,
                errors=[f"Path does not exist: {path}"],
            )

        exclude_patterns = exclude_patterns or []

        # Find all matching files
        files = list(path.glob(pattern))

        # Filter out excluded patterns
        if exclude_patterns:
            filtered_files = []
            for f in files:
                excluded = False
                for exclude in exclude_patterns:
                    if f.match(exclude):
                        excluded = True
                        break
                if not excluded:
                    filtered_files.append(f)
            files = filtered_files

        if not files:
            return ImportResult(
                success=True,
                documents_processed=0,
                errors=["No markdown files found"],
            )

        result = ImportResult(success=True)
        total = len(files)

        for i, file_path in enumerate(files):
            self._report_progress(i + 1, total, f"Processing {file_path.name}")

            try:
                chunks_created = self._import_file(file_path)
                result.documents_processed += 1
                result.chunks_created += chunks_created
            except Exception as e:
                result.errors.append(f"{file_path.name}: {str(e)}")

        return result

    def _import_file(self, file_path: Path) -> int:
        """
        Import a single markdown file.

        Args:
            file_path: Path to the markdown file

        Returns:
            Number of chunks created
        """
        content = file_path.read_text(encoding="utf-8")

        # Parse frontmatter if present
        frontmatter, body = self._parse_frontmatter(content)

        # Build metadata
        metadata = {
            "source": "markdown",
            "file_path": str(file_path),
            "file_name": file_path.name,
            **frontmatter,
        }

        # Extract title from frontmatter or first heading
        title = frontmatter.get("title", "")
        if not title:
            title = self._extract_title(body) or file_path.stem

        metadata["title"] = title

        # Chunk the content
        chunks = self.chunker.chunk_markdown(body, metadata)

        # Generate a stable ID based on file path
        import hashlib
        file_hash = hashlib.sha256(str(file_path).encode()).hexdigest()[:12]
        base_id = f"md_{file_hash}"

        return self._index_chunks(chunks, base_id)

    def _parse_frontmatter(self, content: str) -> tuple[dict, str]:
        """
        Parse YAML frontmatter from markdown content.

        Args:
            content: Full markdown content

        Returns:
            Tuple of (frontmatter_dict, body_content)
        """
        # Check for YAML frontmatter (--- delimited)
        if not content.startswith("---"):
            return {}, content

        # Find the closing ---
        end_match = re.search(r'\n---\s*\n', content[3:])
        if not end_match:
            return {}, content

        frontmatter_str = content[3:3 + end_match.start()]
        body = content[3 + end_match.end():]

        # Parse YAML
        try:
            import yaml
            frontmatter = yaml.safe_load(frontmatter_str) or {}
        except Exception:
            frontmatter = {}

        return frontmatter, body

    def _extract_title(self, content: str) -> str | None:
        """Extract title from first H1 heading."""
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return None

    def import_file(
        self,
        file_path: Path | str,
        metadata: dict | None = None,
    ) -> ImportResult:
        """
        Import a single markdown file.

        Args:
            file_path: Path to the markdown file
            metadata: Additional metadata to include

        Returns:
            ImportResult with statistics
        """
        file_path = Path(file_path)
        if not file_path.exists():
            return ImportResult(
                success=False,
                errors=[f"File does not exist: {file_path}"],
            )

        result = ImportResult(success=True)

        try:
            content = file_path.read_text(encoding="utf-8")
            frontmatter, body = self._parse_frontmatter(content)

            # Merge metadata
            full_metadata = {
                "source": "markdown",
                "file_path": str(file_path),
                "file_name": file_path.name,
                **frontmatter,
                **(metadata or {}),
            }

            # Get title
            title = full_metadata.get("title") or self._extract_title(body) or file_path.stem
            full_metadata["title"] = title

            # Chunk and index
            chunks = self.chunker.chunk_markdown(body, full_metadata)

            import hashlib
            file_hash = hashlib.sha256(str(file_path).encode()).hexdigest()[:12]
            base_id = f"md_{file_hash}"

            result.chunks_created = self._index_chunks(chunks, base_id)
            result.documents_processed = 1

        except Exception as e:
            result.success = False
            result.errors.append(str(e))

        return result
