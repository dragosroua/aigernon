"""File system tools: read, write, edit."""

from pathlib import Path
from typing import Any

from aigernon.agent.tools.base import Tool


def _is_memory_file(path: str) -> bool:
    """Return True if path looks like a memory markdown file."""
    p = path.replace("\\", "/")
    return "/memory/" in p and p.endswith(".md")


def _index_memory_to_chroma(path: str, content: str) -> None:
    """Best-effort: index memory file content into ChromaDB."""
    try:
        from aigernon.config.loader import load_config, get_data_dir
        from aigernon.memory.vector import create_vector_store
        config = load_config()
        data_dir = get_data_dir()
        vs = create_vector_store(
            data_dir=data_dir,
            api_key=config.get_api_key(),
            api_base=config.get_api_base(),
            embedding_model=config.vector.embedding_model,
        )
        p = path.replace("\\", "/")
        collection = "global_memories" if "/global/" in p else "memories"
        filename = Path(path).name
        vs.add(
            collection=collection,
            documents=[content],
            metadatas=[{"source": path, "title": filename, "type": "memory_file"}],
        )
    except Exception:
        pass


def _resolve_path(path: str, allowed_dir: Path | None = None) -> Path:
    """Resolve path and optionally enforce directory restriction."""
    resolved = Path(path).expanduser().resolve()
    if allowed_dir and not str(resolved).startswith(str(allowed_dir.resolve())):
        raise PermissionError(f"Path outside allowed directory: {resolved}")
    return resolved


class ReadFileTool(Tool):
    """Tool to read file contents."""
    
    def __init__(self, allowed_dir: Path | None = None):
        self._allowed_dir = allowed_dir

    @property
    def name(self) -> str:
        return "read_file"
    
    @property
    def description(self) -> str:
        return "Read the contents of a file at the given path."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path to read"
                }
            },
            "required": ["path"]
        }
    
    async def execute(self, path: str, _allowed_dir: Path | None = None, **kwargs: Any) -> str:
        try:
            effective_dir = _allowed_dir or self._allowed_dir
            file_path = _resolve_path(path, effective_dir)
            if not file_path.exists():
                return f"Error: File not found: {path}"
            if not file_path.is_file():
                return f"Error: Not a file: {path}"
            content = file_path.read_text(encoding="utf-8")
            return content
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error reading file: {str(e)}"


class WriteFileTool(Tool):
    """Tool to write content to a file."""
    
    def __init__(self, allowed_dir: Path | None = None):
        self._allowed_dir = allowed_dir

    @property
    def name(self) -> str:
        return "write_file"
    
    @property
    def description(self) -> str:
        return "Write content to a file at the given path. Creates parent directories if needed."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path to write to"
                },
                "content": {
                    "type": "string",
                    "description": "The content to write"
                }
            },
            "required": ["path", "content"]
        }
    
    async def execute(self, path: str, content: str, _allowed_dir: Path | None = None, **kwargs: Any) -> str:
        try:
            effective_dir = _allowed_dir or self._allowed_dir
            file_path = _resolve_path(path, effective_dir)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            if _is_memory_file(path):
                _index_memory_to_chroma(path, content)
            return f"Successfully wrote {len(content)} bytes to {path}"
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error writing file: {str(e)}"


class EditFileTool(Tool):
    """Tool to edit a file by replacing text."""
    
    def __init__(self, allowed_dir: Path | None = None):
        self._allowed_dir = allowed_dir

    @property
    def name(self) -> str:
        return "edit_file"
    
    @property
    def description(self) -> str:
        return "Edit a file by replacing old_text with new_text. The old_text must exist exactly in the file."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path to edit"
                },
                "old_text": {
                    "type": "string",
                    "description": "The exact text to find and replace"
                },
                "new_text": {
                    "type": "string",
                    "description": "The text to replace with"
                }
            },
            "required": ["path", "old_text", "new_text"]
        }
    
    async def execute(self, path: str, old_text: str, new_text: str, _allowed_dir: Path | None = None, **kwargs: Any) -> str:
        try:
            effective_dir = _allowed_dir or self._allowed_dir
            file_path = _resolve_path(path, effective_dir)
            if not file_path.exists():
                return f"Error: File not found: {path}"
            content = file_path.read_text(encoding="utf-8")
            if old_text not in content:
                return f"Error: old_text not found in file. Make sure it matches exactly."
            count = content.count(old_text)
            if count > 1:
                return f"Warning: old_text appears {count} times. Please provide more context to make it unique."
            new_content = content.replace(old_text, new_text, 1)
            file_path.write_text(new_content, encoding="utf-8")
            if _is_memory_file(path):
                _index_memory_to_chroma(path, new_content)
            return f"Successfully edited {path}"
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error editing file: {str(e)}"


class ListDirTool(Tool):
    """Tool to list directory contents."""
    
    def __init__(self, allowed_dir: Path | None = None):
        self._allowed_dir = allowed_dir

    @property
    def name(self) -> str:
        return "list_dir"
    
    @property
    def description(self) -> str:
        return "List the contents of a directory."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The directory path to list"
                }
            },
            "required": ["path"]
        }
    
    async def execute(self, path: str, _allowed_dir: Path | None = None, **kwargs: Any) -> str:
        try:
            effective_dir = _allowed_dir or self._allowed_dir
            dir_path = _resolve_path(path, effective_dir)
            if not dir_path.exists():
                return f"Error: Directory not found: {path}"
            if not dir_path.is_dir():
                return f"Error: Not a directory: {path}"
            items = []
            for item in sorted(dir_path.iterdir()):
                prefix = "📁 " if item.is_dir() else "📄 "
                items.append(f"{prefix}{item.name}")
            if not items:
                return f"Directory {path} is empty"
            return "\n".join(items)
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error listing directory: {str(e)}"
