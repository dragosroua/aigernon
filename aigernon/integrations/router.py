"""Channel router: fans out agent output to linked external channels."""

from typing import Optional, TYPE_CHECKING
from loguru import logger

if TYPE_CHECKING:
    from aigernon.integrations.email.sender import EmailSender
    from aigernon.integrations.telegram.sender import TelegramSender


class ChannelRouter:
    """Deliver text to all channels linked for a user."""

    def __init__(
        self,
        db=None,
        email_sender: Optional["EmailSender"] = None,
        telegram_sender: Optional["TelegramSender"] = None,
    ):
        self.db = db
        self.email_sender = email_sender
        self.telegram_sender = telegram_sender

    async def deliver(self, user_id: str, subject: str, text: str, channels: list[str] | None = None) -> None:
        """Fan out to linked channels for this user. Pass channels to restrict delivery."""
        if not self.db:
            return
        try:
            links = await self.db.list_channel_links(user_id)
        except Exception as e:
            logger.warning(f"ChannelRouter: failed to load links for {user_id}: {e}")
            return

        for link in links:
            if channels is not None and link["channel"] not in channels:
                continue
            try:
                await self._send(link["channel"], link["external_id"], subject, text)
            except Exception as e:
                logger.warning(f"ChannelRouter: delivery to {link['channel']} failed: {e}")

    async def deliver_to(self, channel: str, external_id: str, subject: str, text: str) -> None:
        """Deliver directly to a specific channel + external_id (no DB lookup)."""
        await self._send(channel, external_id, subject, text)

    async def _send(self, channel: str, external_id: str, subject: str, text: str) -> None:
        if channel == "email":
            if self.email_sender:
                await self.email_sender.send(to=external_id, subject=subject, text=text)
            else:
                logger.warning("ChannelRouter: email sender not configured")
        elif channel == "telegram":
            if self.telegram_sender:
                msg = f"*{subject}*\n\n{text}" if subject else text
                await self.telegram_sender.send(chat_id=external_id, text=msg)
            else:
                logger.warning("ChannelRouter: telegram sender not configured")
        else:
            logger.warning(f"ChannelRouter: unknown channel '{channel}'")
