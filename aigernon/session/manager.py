"""Session management — SQLite persistence with Fernet encryption at rest."""

import json
import sqlite3
import threading
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from loguru import logger


# ── Encryption helpers ─────────────────────────────────────────────────────────

def _encrypt(plaintext: str) -> str:
    """Encrypt message content with Fernet. Falls back to plaintext if key unset."""
    try:
        from aigernon.security.crypto import encrypt_token
        return encrypt_token(plaintext)
    except Exception as exc:
        logger.warning(f"Message encryption unavailable ({exc}); storing plaintext.")
        return plaintext


def _decrypt(value: str) -> str:
    """Decrypt message content. Returns value as-is if decryption fails."""
    try:
        from aigernon.security.crypto import decrypt_token_safe
        result = decrypt_token_safe(value)
        return result if result is not None else value
    except Exception:
        return value


def _extract_user_id(session_key: str) -> "str | None":
    """Extract user_id from keys of the form 'web:{user_id}:...'."""
    parts = session_key.split(":", 2)
    if len(parts) >= 2 and parts[0] == "web":
        return parts[1]
    return None


# ── Session dataclass (unchanged public interface) ─────────────────────────────

@dataclass
class Session:
    """A conversation session."""

    key: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self, ttl_hours: int) -> bool:
        if ttl_hours <= 0:
            return False
        return datetime.now() > self.updated_at + timedelta(hours=ttl_hours)

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        msg = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs,
        }
        self.messages.append(msg)
        self.updated_at = datetime.now()

    def get_history(self, max_messages: int = 50) -> list[dict[str, Any]]:
        recent = self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages
        return [{"role": m["role"], "content": m["content"]} for m in recent]

    def clear(self) -> None:
        self.messages = []
        self.updated_at = datetime.now()


# ── SessionManager ─────────────────────────────────────────────────────────────

class SessionManager:
    """
    Manages conversation sessions with SQLite persistence and encryption at rest.

    Design:
    - Message content is Fernet-encrypted before INSERT, decrypted on SELECT.
      Requires FERNET_KEY env var; falls back to plaintext with a warning.
    - Messages are appended incrementally (no DELETE+reinsert on every save).
    - Sessions older than retention_days are purged once per hour.
    - ttl_hours=0 (default) means sessions never expire on inactivity —
      history persists across logins.
    """

    DEFAULT_RETENTION_DAYS = 90
    # Max messages to load from DB per session (recent history window).
    # The full archive stays in DB; only the window is held in memory.
    _LOAD_LIMIT = 200

    def __init__(
        self,
        workspace: Path,            # kept for API compatibility, not used for DB path
        ttl_hours: int = 0,         # 0 = no inactivity expiry (history survives logins)
        retention_days: int = DEFAULT_RETENTION_DAYS,
    ):
        self.ttl_hours = ttl_hours
        self.retention_days = retention_days
        self._cache: dict[str, Session] = {}
        self._persisted_count: dict[str, int] = {}  # session_key → #messages already in DB
        self._lock = threading.Lock()
        self._last_cleanup = datetime.now()

        # Resolve DB path: /data volume in Docker, ~/.aigernon/data locally
        data_dir = Path("/data") if Path("/data").exists() else Path.home() / ".aigernon" / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = data_dir / "sessions.db"

        self._init_db()
        logger.info(f"SessionManager ready — DB: {self._db_path}")

    # ── DB helpers ─────────────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    key         TEXT PRIMARY KEY,
                    user_id     TEXT,
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL,
                    metadata    TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS chat_messages (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_key  TEXT NOT NULL,
                    role         TEXT NOT NULL,
                    content      TEXT NOT NULL,
                    timestamp    TEXT NOT NULL,
                    FOREIGN KEY (session_key)
                        REFERENCES chat_sessions(key)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session
                    ON chat_messages(session_key, id);
                CREATE INDEX IF NOT EXISTS idx_sessions_user
                    ON chat_sessions(user_id);
                CREATE INDEX IF NOT EXISTS idx_sessions_updated
                    ON chat_sessions(updated_at);
            """)

    # ── Retention cleanup ──────────────────────────────────────────────────────

    def _cleanup_if_due(self) -> None:
        if (datetime.now() - self._last_cleanup).total_seconds() < 3600:
            return
        self._last_cleanup = datetime.now()
        cutoff = (datetime.now() - timedelta(days=self.retention_days)).isoformat()
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    "DELETE FROM chat_sessions WHERE updated_at < ?", (cutoff,)
                )
                removed = cursor.rowcount
            if removed:
                # Evict deleted sessions from cache
                with self._lock:
                    stale = [k for k in self._cache if
                             self._cache[k].updated_at < datetime.now() - timedelta(days=self.retention_days)]
                    for k in stale:
                        self._cache.pop(k, None)
                        self._persisted_count.pop(k, None)
                logger.info(f"Session retention: removed {removed} sessions older than {self.retention_days}d")
        except Exception as exc:
            logger.warning(f"Session cleanup failed: {exc}")

    # ── Core interface ─────────────────────────────────────────────────────────

    def get_or_create(self, key: str) -> Session:
        self._cleanup_if_due()

        with self._lock:
            if key in self._cache:
                session = self._cache[key]
                if session.is_expired(self.ttl_hours):
                    logger.info(f"Session expired (cache): {key}")
                    self._evict(key)
                    session = Session(key=key)
                    self._cache[key] = session
                    self._persisted_count[key] = 0
                return session

        session = self._load(key)
        if session is None:
            session = Session(key=key)
            with self._lock:
                self._persisted_count[key] = 0
        elif session.is_expired(self.ttl_hours):
            logger.info(f"Session expired (db): {key}")
            self.delete(key)
            session = Session(key=key)
            with self._lock:
                self._persisted_count[key] = 0

        with self._lock:
            self._cache[key] = session
        return session

    def _load(self, key: str) -> "Session | None":
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM chat_sessions WHERE key = ?", (key,)
                ).fetchone()
                if not row:
                    return None

                msg_rows = conn.execute(
                    """SELECT role, content, timestamp
                       FROM chat_messages
                       WHERE session_key = ?
                       ORDER BY id DESC
                       LIMIT ?""",
                    (key, self._LOAD_LIMIT),
                ).fetchall()

            # Rows are DESC, reverse to chronological order
            msg_rows = list(reversed(msg_rows))

            messages = []
            for m in msg_rows:
                messages.append({
                    "role": m["role"],
                    "content": _decrypt(m["content"]),
                    "timestamp": m["timestamp"],
                })

            with self._lock:
                # Track how many messages are already in DB for this session
                self._persisted_count[key] = len(messages)

            return Session(
                key=key,
                messages=messages,
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                metadata=json.loads(row["metadata"] or "{}"),
            )
        except Exception as exc:
            logger.warning(f"Failed to load session {key}: {exc}")
            return None

    def save(self, session: Session) -> None:
        """Persist new messages and update the session row."""
        with self._lock:
            persisted = self._persisted_count.get(session.key, 0)

        new_messages = session.messages[persisted:]
        user_id = _extract_user_id(session.key)
        now = session.updated_at.isoformat()

        try:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO chat_sessions
                           (key, user_id, created_at, updated_at, metadata)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(key) DO UPDATE SET
                           updated_at = excluded.updated_at,
                           metadata   = excluded.metadata""",
                    (
                        session.key,
                        user_id,
                        session.created_at.isoformat(),
                        now,
                        json.dumps(session.metadata),
                    ),
                )
                for msg in new_messages:
                    conn.execute(
                        """INSERT INTO chat_messages
                               (session_key, role, content, timestamp)
                           VALUES (?, ?, ?, ?)""",
                        (
                            session.key,
                            msg["role"],
                            _encrypt(msg["content"]),
                            msg.get("timestamp", now),
                        ),
                    )
        except Exception as exc:
            logger.error(f"Failed to save session {session.key}: {exc}")
            return

        with self._lock:
            self._cache[session.key] = session
            self._persisted_count[session.key] = len(session.messages)

    def delete(self, key: str) -> bool:
        self._evict(key)
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    "DELETE FROM chat_sessions WHERE key = ?", (key,)
                )
                return cursor.rowcount > 0
        except Exception as exc:
            logger.warning(f"Failed to delete session {key}: {exc}")
            return False

    def delete_user_sessions(self, user_id: str) -> int:
        """Delete all sessions for a user (call on account deletion). Returns count."""
        with self._lock:
            stale_keys = [k for k in self._cache if _extract_user_id(k) == user_id]
            for k in stale_keys:
                self._cache.pop(k, None)
                self._persisted_count.pop(k, None)
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    "DELETE FROM chat_sessions WHERE user_id = ?", (user_id,)
                )
                return cursor.rowcount
        except Exception as exc:
            logger.warning(f"Failed to delete sessions for user {user_id}: {exc}")
            return 0

    def list_sessions(self) -> list[dict[str, Any]]:
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """SELECT key, user_id, created_at, updated_at
                       FROM chat_sessions
                       ORDER BY updated_at DESC"""
                ).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.warning(f"Failed to list sessions: {exc}")
            return []

    # ── Internal ───────────────────────────────────────────────────────────────

    def _evict(self, key: str) -> None:
        """Remove a session from the in-memory cache."""
        self._cache.pop(key, None)
        self._persisted_count.pop(key, None)
