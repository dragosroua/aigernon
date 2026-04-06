"""WebSocket connection manager."""

import asyncio
import json
from typing import Dict, Set, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger


@dataclass
class Connection:
    """WebSocket connection."""
    websocket: WebSocket
    user_id: str
    session_id: str
    connected_at: datetime = field(default_factory=datetime.utcnow)

    def __hash__(self):
        return id(self.websocket)

    def __eq__(self, other):
        if not isinstance(other, Connection):
            return False
        return self.websocket is other.websocket


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        # user_id -> set of connections
        self._connections: Dict[str, Set[Connection]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: str, session_id: str) -> Connection:
        """Accept and register a new connection."""
        await websocket.accept()

        connection = Connection(
            websocket=websocket,
            user_id=user_id,
            session_id=session_id,
        )

        async with self._lock:
            if user_id not in self._connections:
                self._connections[user_id] = set()
            self._connections[user_id].add(connection)

        logger.info(f"WebSocket connected: user={user_id}, session={session_id}")
        return connection

    async def disconnect(self, connection: Connection):
        """Remove a connection."""
        async with self._lock:
            user_id = connection.user_id
            if user_id in self._connections:
                self._connections[user_id].discard(connection)
                if not self._connections[user_id]:
                    del self._connections[user_id]

        logger.info(f"WebSocket disconnected: user={connection.user_id}")

    def is_connected(self, user_id: str) -> bool:
        """Check if user has any active connections."""
        return user_id in self._connections and len(self._connections[user_id]) > 0

    async def send_to_user(self, user_id: str, message: dict):
        """Send message to all connections for a user."""
        if user_id not in self._connections:
            return

        data = json.dumps(message)
        dead_connections = []

        for connection in self._connections[user_id]:
            try:
                await connection.websocket.send_text(data)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                dead_connections.append(connection)

        # Clean up dead connections
        for connection in dead_connections:
            await self.disconnect(connection)

    async def send_to_session(self, user_id: str, session_id: str, message: dict):
        """Send message to specific session."""
        if user_id not in self._connections:
            return

        data = json.dumps(message)

        for connection in self._connections[user_id]:
            if connection.session_id == session_id:
                try:
                    await connection.websocket.send_text(data)
                except Exception as e:
                    logger.warning(f"Failed to send to WebSocket: {e}")

    async def broadcast(self, message: dict):
        """Broadcast to all connected users."""
        data = json.dumps(message)

        for user_id, connections in self._connections.items():
            for connection in connections:
                try:
                    await connection.websocket.send_text(data)
                except Exception:
                    pass

    def get_connection_count(self) -> int:
        """Get total number of connections."""
        return sum(len(conns) for conns in self._connections.values())

    def get_user_count(self) -> int:
        """Get number of connected users."""
        return len(self._connections)


class WebSocketManager:
    """High-level WebSocket manager with event handling."""

    def __init__(self, connection_manager: ConnectionManager):
        self.connections = connection_manager
        self._event_handlers: Dict[str, list] = {}

    def on_event(self, event_type: str):
        """Decorator to register event handler."""
        def decorator(func):
            if event_type not in self._event_handlers:
                self._event_handlers[event_type] = []
            self._event_handlers[event_type].append(func)
            return func
        return decorator

    async def handle_message(self, connection: Connection, data: dict):
        """Handle incoming WebSocket message."""
        event_type = data.get("type")
        if not event_type:
            return

        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                await handler(connection, data)
            except Exception as e:
                logger.error(f"Error in WebSocket handler: {e}")

    async def send_chat_message(
        self,
        user_id: str,
        session_id: str,
        content: str,
        realm: Optional[str] = None,
        is_streaming: bool = False,
        is_complete: bool = False,
    ):
        """Send chat message to user."""
        await self.connections.send_to_session(user_id, session_id, {
            "type": "chat_message",
            "content": content,
            "realm": realm,
            "is_streaming": is_streaming,
            "is_complete": is_complete,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def send_realm_change(
        self,
        user_id: str,
        session_id: str,
        realm: str,
    ):
        """Send realm change event."""
        await self.connections.send_to_session(user_id, session_id, {
            "type": "realm_change",
            "realm": realm,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def send_notification(
        self,
        user_id: str,
        notification: dict,
    ):
        """Send notification to user."""
        await self.connections.send_to_user(user_id, {
            "type": "notification",
            **notification,
        })

    async def send_typing_indicator(
        self,
        user_id: str,
        session_id: str,
        is_typing: bool,
    ):
        """Send typing indicator."""
        await self.connections.send_to_session(user_id, session_id, {
            "type": "typing",
            "is_typing": is_typing,
        })
