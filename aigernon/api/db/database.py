"""SQLite database for users and notifications."""

import aiosqlite
from pathlib import Path
from datetime import datetime
from typing import Optional
import json


class Database:
    """Async SQLite database wrapper."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self):
        """Connect to database and ensure schema exists."""
        self._connection = await aiosqlite.connect(str(self.db_path))
        self._connection.row_factory = aiosqlite.Row
        await self._create_tables()

    async def close(self):
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def _create_tables(self):
        """Create tables if they don't exist."""
        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                picture_url TEXT,
                oauth_provider TEXT,
                oauth_sub TEXT,
                theme TEXT DEFAULT 'system',
                created_at TEXT NOT NULL,
                last_login TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                context TEXT,
                project_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT,
                urgency TEXT DEFAULT 'low',
                action_url TEXT,
                created_at TEXT NOT NULL,
                read_at TEXT,
                delivered_via TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
        """)
        await self._connection.commit()

    # User operations
    async def get_user(self, user_id: str) -> Optional[dict]:
        """Get user by ID."""
        async with self._connection.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_user_by_email(self, email: str) -> Optional[dict]:
        """Get user by email."""
        async with self._connection.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def upsert_user(
        self,
        user_id: str,
        email: str,
        name: str = None,
        picture_url: str = None,
        oauth_provider: str = None,
        oauth_sub: str = None,
    ) -> dict:
        """Create or update user."""
        now = datetime.utcnow().isoformat()

        existing = await self.get_user(user_id)
        if existing:
            await self._connection.execute("""
                UPDATE users SET
                    name = COALESCE(?, name),
                    picture_url = COALESCE(?, picture_url),
                    last_login = ?
                WHERE id = ?
            """, (name, picture_url, now, user_id))
        else:
            await self._connection.execute("""
                INSERT INTO users (id, email, name, picture_url, oauth_provider, oauth_sub, created_at, last_login)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, email, name, picture_url, oauth_provider, oauth_sub, now, now))

        await self._connection.commit()
        return await self.get_user(user_id)

    async def update_user_theme(self, user_id: str, theme: str) -> bool:
        """Update user theme preference."""
        await self._connection.execute(
            "UPDATE users SET theme = ? WHERE id = ?", (theme, user_id)
        )
        await self._connection.commit()
        return True

    # Session operations
    async def list_sessions(self, user_id: str) -> list[dict]:
        """List user's sessions."""
        async with self._connection.execute(
            "SELECT * FROM sessions WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_session(self, session_id: str) -> Optional[dict]:
        """Get session by ID."""
        async with self._connection.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def create_session(
        self,
        session_id: str,
        user_id: str,
        name: str,
        context: str = None,
        project_id: str = None,
    ) -> dict:
        """Create a new session."""
        now = datetime.utcnow().isoformat()
        await self._connection.execute("""
            INSERT INTO sessions (id, user_id, name, context, project_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (session_id, user_id, name, context, project_id, now, now))
        await self._connection.commit()
        return await self.get_session(session_id)

    async def update_session(self, session_id: str) -> bool:
        """Update session timestamp."""
        now = datetime.utcnow().isoformat()
        await self._connection.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id)
        )
        await self._connection.commit()
        return True

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        await self._connection.execute(
            "DELETE FROM sessions WHERE id = ?", (session_id,)
        )
        await self._connection.commit()
        return True

    # Notification operations
    async def list_notifications(
        self,
        user_id: str,
        limit: int = 50,
        unread_only: bool = False,
    ) -> list[dict]:
        """List user's notifications."""
        query = "SELECT * FROM notifications WHERE user_id = ?"
        params = [user_id]

        if unread_only:
            query += " AND read_at IS NULL"

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        async with self._connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def create_notification(
        self,
        notification_id: str,
        user_id: str,
        type: str,
        title: str,
        body: str = None,
        urgency: str = "low",
        action_url: str = None,
    ) -> dict:
        """Create a notification."""
        now = datetime.utcnow().isoformat()
        await self._connection.execute("""
            INSERT INTO notifications (id, user_id, type, title, body, urgency, action_url, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (notification_id, user_id, type, title, body, urgency, action_url, now))
        await self._connection.commit()

        async with self._connection.execute(
            "SELECT * FROM notifications WHERE id = ?", (notification_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row)

    async def mark_notification_read(self, notification_id: str) -> bool:
        """Mark notification as read."""
        now = datetime.utcnow().isoformat()
        await self._connection.execute(
            "UPDATE notifications SET read_at = ? WHERE id = ?", (now, notification_id)
        )
        await self._connection.commit()
        return True

    async def mark_all_notifications_read(self, user_id: str) -> int:
        """Mark all notifications as read for user."""
        now = datetime.utcnow().isoformat()
        cursor = await self._connection.execute(
            "UPDATE notifications SET read_at = ? WHERE user_id = ? AND read_at IS NULL",
            (now, user_id)
        )
        await self._connection.commit()
        return cursor.rowcount

    async def count_unread_notifications(self, user_id: str) -> int:
        """Count unread notifications."""
        async with self._connection.execute(
            "SELECT COUNT(*) as count FROM notifications WHERE user_id = ? AND read_at IS NULL",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row["count"]
