"""Base channel interface for chat platforms."""

from abc import ABC, abstractmethod
from typing import Any

from loguru import logger

from aigernon.bus.events import InboundMessage, OutboundMessage
from aigernon.bus.queue import MessageBus
from aigernon.security.rate_limiter import RateLimiter, RateLimitConfig
from aigernon.security.audit import AuditLogger


class BaseChannel(ABC):
    """
    Abstract base class for chat channel implementations.

    Each channel (Telegram, Discord, etc.) should implement this interface
    to integrate with the aigernon message bus.
    """

    name: str = "base"

    # Shared instances across all channels
    _rate_limiter: RateLimiter | None = None
    _audit_logger: AuditLogger | None = None

    def __init__(self, config: Any, bus: MessageBus):
        """
        Initialize the channel.

        Args:
            config: Channel-specific configuration.
            bus: The message bus for communication.
        """
        self.config = config
        self.bus = bus
        self._running = False

        # Initialize shared rate limiter (once per class)
        if BaseChannel._rate_limiter is None:
            BaseChannel._rate_limiter = RateLimiter(RateLimitConfig())

        # Initialize shared audit logger (once per class)
        if BaseChannel._audit_logger is None:
            BaseChannel._audit_logger = AuditLogger()
    
    @abstractmethod
    async def start(self) -> None:
        """
        Start the channel and begin listening for messages.
        
        This should be a long-running async task that:
        1. Connects to the chat platform
        2. Listens for incoming messages
        3. Forwards messages to the bus via _handle_message()
        """
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the channel and clean up resources."""
        pass
    
    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None:
        """
        Send a message through this channel.
        
        Args:
            msg: The message to send.
        """
        pass
    
    def is_allowed(self, sender_id: str) -> bool:
        """
        Check if a sender is allowed to use this bot.
        
        Args:
            sender_id: The sender's identifier.
        
        Returns:
            True if allowed, False otherwise.
        """
        allow_list = getattr(self.config, "allow_from", [])
        
        # If no allow list, allow everyone
        if not allow_list:
            return True
        
        sender_str = str(sender_id)
        if sender_str in allow_list:
            return True
        if "|" in sender_str:
            for part in sender_str.split("|"):
                if part and part in allow_list:
                    return True
        return False
    
    async def _handle_message(
        self,
        sender_id: str,
        chat_id: str,
        content: str,
        media: list[str] | None = None,
        metadata: dict[str, Any] | None = None
    ) -> None:
        """
        Handle an incoming message from the chat platform.

        This method checks permissions, rate limits, and forwards to the bus.

        Args:
            sender_id: The sender's identifier.
            chat_id: The chat/channel identifier.
            content: Message text content.
            media: Optional list of media URLs.
            metadata: Optional channel-specific metadata.
        """
        sender_str = str(sender_id)

        # Check access permission
        if not self.is_allowed(sender_id):
            logger.warning(
                f"Access denied for sender {sender_id} on channel {self.name}. "
                f"Add them to allowFrom list in config to grant access."
            )
            if self._audit_logger:
                self._audit_logger.log_access_denied(
                    sender_str, self.name, "not_in_allowlist"
                )
            return

        # Check rate limit
        if self._rate_limiter:
            allowed, reason = self._rate_limiter.check(sender_str)
            if not allowed:
                logger.warning(f"Rate limited sender {sender_id} on channel {self.name}: {reason}")
                if self._audit_logger:
                    self._audit_logger.log_rate_limited(sender_str, self.name, "message_rate")
                # Optionally send a rate limit message back
                await self._send_rate_limit_response(chat_id, reason)
                return

        msg = InboundMessage(
            channel=self.name,
            sender_id=sender_str,
            chat_id=str(chat_id),
            content=content,
            media=media or [],
            metadata=metadata or {}
        )

        await self.bus.publish_inbound(msg)

    async def _send_rate_limit_response(self, chat_id: str, reason: str | None) -> None:
        """
        Send a rate limit response to the user.

        Subclasses can override this to customize the response.
        Default implementation does nothing (silent rate limit).
        """
        pass
    
    @property
    def is_running(self) -> bool:
        """Check if the channel is running."""
        return self._running
