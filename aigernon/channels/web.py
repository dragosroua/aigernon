"""Web channel for FastAPI/WebSocket integration."""

from typing import Any, Optional
from dataclasses import dataclass

from loguru import logger

from aigernon.bus.events import InboundMessage, OutboundMessage
from aigernon.bus.queue import MessageBus
from aigernon.channels.base import BaseChannel


@dataclass
class WebChannelConfig:
    """Web channel configuration."""
    enabled: bool = True
    allow_from: list[str] = None  # Empty = allow all authenticated users

    def __post_init__(self):
        if self.allow_from is None:
            self.allow_from = []


class WebChannel(BaseChannel):
    """
    Web channel that bridges FastAPI WebSocket connections to the message bus.

    This channel is used by the web UI to communicate with the agent.
    Unlike other channels, it doesn't start its own listener - it receives
    messages from the API routes and sends responses via WebSocket.
    """

    name = "web"

    def __init__(
        self,
        config: WebChannelConfig,
        bus: MessageBus,
        ws_manager: Optional[Any] = None,
    ):
        """
        Initialize the web channel.

        Args:
            config: Channel configuration.
            bus: Message bus for communication.
            ws_manager: WebSocketManager instance for sending responses.
        """
        super().__init__(config, bus)
        self.ws_manager = ws_manager

    async def start(self) -> None:
        """
        Start the web channel.

        The web channel doesn't need a listener loop - it receives messages
        directly from API routes and sends responses via WebSocket.
        """
        self._running = True
        logger.info("Web channel started")

        # Subscribe to outbound messages for this channel
        while self._running:
            try:
                msg = await self.bus.consume_outbound_for_channel("web")
                if msg:
                    await self.send(msg)
            except Exception as e:
                if self._running:
                    logger.error(f"Error in web channel loop: {e}")

    async def stop(self) -> None:
        """Stop the web channel."""
        self._running = False
        logger.info("Web channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        """
        Send a message through the web channel.

        Args:
            msg: The message to send via WebSocket.
        """
        if not self.ws_manager:
            logger.warning("WebSocketManager not set, cannot send message")
            return

        # Parse chat_id to get user_id and session_id
        # Format: web:{user_id}:{session_id}
        parts = msg.chat_id.split(":")
        if len(parts) >= 3:
            user_id = parts[1]
            session_id = parts[2] if len(parts) > 2 else "default"
        else:
            user_id = msg.chat_id
            session_id = "default"

        try:
            await self.ws_manager.send_chat_message(
                user_id=user_id,
                session_id=session_id,
                content=msg.content,
                realm=msg.metadata.get("realm") if msg.metadata else None,
                is_complete=True,
            )
        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {e}")

    async def handle_api_message(
        self,
        user_id: str,
        session_id: str,
        content: str,
        metadata: dict[str, Any] = None,
    ) -> None:
        """
        Handle a message from the API (called by API routes).

        Args:
            user_id: User ID from authentication.
            session_id: Session ID.
            content: Message content.
            metadata: Optional metadata.
        """
        chat_id = f"web:{user_id}:{session_id}"

        await self._handle_message(
            sender_id=user_id,
            chat_id=chat_id,
            content=content,
            metadata=metadata,
        )

    def set_ws_manager(self, ws_manager: Any) -> None:
        """Set the WebSocketManager instance."""
        self.ws_manager = ws_manager
