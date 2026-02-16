"""Session management for conversation history."""

import json
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from aigernon.utils.helpers import ensure_dir, safe_filename


@dataclass
class Session:
    """
    A conversation session.

    Stores messages in JSONL format for easy reading and persistence.
    """

    key: str  # channel:chat_id
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self, ttl_hours: int) -> bool:
        """Check if session has expired based on TTL."""
        if ttl_hours <= 0:
            return False  # No expiry
        expiry_time = self.updated_at + timedelta(hours=ttl_hours)
        return datetime.now() > expiry_time
    
    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """Add a message to the session."""
        msg = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.messages.append(msg)
        self.updated_at = datetime.now()
    
    def get_history(self, max_messages: int = 50) -> list[dict[str, Any]]:
        """
        Get message history for LLM context.
        
        Args:
            max_messages: Maximum messages to return.
        
        Returns:
            List of messages in LLM format.
        """
        # Get recent messages
        recent = self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages
        
        # Convert to LLM format (just role and content)
        return [{"role": m["role"], "content": m["content"]} for m in recent]
    
    def clear(self) -> None:
        """Clear all messages in the session."""
        self.messages = []
        self.updated_at = datetime.now()


class SessionManager:
    """
    Manages conversation sessions.

    Sessions are stored as JSONL files in the sessions directory.
    Supports TTL-based expiry and automatic cleanup.
    """

    def __init__(self, workspace: Path, ttl_hours: int = 24):
        """
        Initialize session manager.

        Args:
            workspace: Workspace directory.
            ttl_hours: Session TTL in hours (0 = no expiry).
        """
        self.workspace = workspace
        self.sessions_dir = ensure_dir(Path.home() / ".aigernon" / "sessions")
        self.ttl_hours = ttl_hours
        self._cache: dict[str, Session] = {}
        self._last_cleanup = datetime.now()
    
    def _get_session_path(self, key: str) -> Path:
        """Get the file path for a session."""
        safe_key = safe_filename(key.replace(":", "_"))
        return self.sessions_dir / f"{safe_key}.jsonl"
    
    def get_or_create(self, key: str) -> Session:
        """
        Get an existing session or create a new one.

        Expired sessions are automatically cleared and a new session is created.

        Args:
            key: Session key (usually channel:chat_id).

        Returns:
            The session.
        """
        # Periodic cleanup (every hour)
        if (datetime.now() - self._last_cleanup).total_seconds() > 3600:
            self._cleanup_expired()

        # Check cache
        if key in self._cache:
            session = self._cache[key]
            # Check if expired
            if session.is_expired(self.ttl_hours):
                logger.info(f"Session expired: {key}")
                self.delete(key)
                session = Session(key=key)
                self._cache[key] = session
            return session

        # Try to load from disk
        session = self._load(key)
        if session is None:
            session = Session(key=key)
        elif session.is_expired(self.ttl_hours):
            # Loaded but expired
            logger.info(f"Session expired (on load): {key}")
            self.delete(key)
            session = Session(key=key)

        self._cache[key] = session
        return session

    def _cleanup_expired(self) -> int:
        """
        Clean up expired sessions from disk.

        Returns:
            Number of sessions cleaned up.
        """
        if self.ttl_hours <= 0:
            return 0  # No expiry configured

        cleaned = 0
        self._last_cleanup = datetime.now()

        # Check cached sessions
        expired_keys = [
            key for key, session in self._cache.items()
            if session.is_expired(self.ttl_hours)
        ]
        for key in expired_keys:
            self.delete(key)
            cleaned += 1

        # Check on-disk sessions not in cache
        for path in self.sessions_dir.glob("*.jsonl"):
            try:
                with open(path) as f:
                    first_line = f.readline().strip()
                    if first_line:
                        data = json.loads(first_line)
                        if data.get("_type") == "metadata":
                            updated_at = data.get("updated_at")
                            if updated_at:
                                updated = datetime.fromisoformat(updated_at)
                                if (datetime.now() - updated).total_seconds() > self.ttl_hours * 3600:
                                    path.unlink()
                                    cleaned += 1
                                    logger.debug(f"Cleaned expired session file: {path.name}")
            except Exception:
                continue

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} expired sessions")

        return cleaned
    
    def _load(self, key: str) -> Session | None:
        """Load a session from disk."""
        path = self._get_session_path(key)
        
        if not path.exists():
            return None
        
        try:
            messages = []
            metadata = {}
            created_at = None
            
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    data = json.loads(line)
                    
                    if data.get("_type") == "metadata":
                        metadata = data.get("metadata", {})
                        created_at = datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
                    else:
                        messages.append(data)
            
            return Session(
                key=key,
                messages=messages,
                created_at=created_at or datetime.now(),
                metadata=metadata
            )
        except Exception as e:
            logger.warning(f"Failed to load session {key}: {e}")
            return None
    
    def save(self, session: Session) -> None:
        """Save a session to disk."""
        path = self._get_session_path(session.key)
        
        with open(path, "w") as f:
            # Write metadata first
            metadata_line = {
                "_type": "metadata",
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "metadata": session.metadata
            }
            f.write(json.dumps(metadata_line) + "\n")
            
            # Write messages
            for msg in session.messages:
                f.write(json.dumps(msg) + "\n")
        
        self._cache[session.key] = session
    
    def delete(self, key: str) -> bool:
        """
        Delete a session.
        
        Args:
            key: Session key.
        
        Returns:
            True if deleted, False if not found.
        """
        # Remove from cache
        self._cache.pop(key, None)
        
        # Remove file
        path = self._get_session_path(key)
        if path.exists():
            path.unlink()
            return True
        return False
    
    def list_sessions(self) -> list[dict[str, Any]]:
        """
        List all sessions.
        
        Returns:
            List of session info dicts.
        """
        sessions = []
        
        for path in self.sessions_dir.glob("*.jsonl"):
            try:
                # Read just the metadata line
                with open(path) as f:
                    first_line = f.readline().strip()
                    if first_line:
                        data = json.loads(first_line)
                        if data.get("_type") == "metadata":
                            sessions.append({
                                "key": path.stem.replace("_", ":"),
                                "created_at": data.get("created_at"),
                                "updated_at": data.get("updated_at"),
                                "path": str(path)
                            })
            except Exception:
                continue
        
        return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)
