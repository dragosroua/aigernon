"""Telegram Bot API sender."""

from loguru import logger


class TelegramSender:
    """Send messages via Telegram Bot API."""

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self._base = f"https://api.telegram.org/bot{bot_token}"

    async def send(self, chat_id: str, text: str) -> bool:
        try:
            import httpx

            # Telegram has a 4096 char limit; split if needed
            chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)]
            async with httpx.AsyncClient() as client:
                for chunk in chunks:
                    resp = await client.post(
                        f"{self._base}/sendMessage",
                        json={"chat_id": chat_id, "text": chunk, "parse_mode": "Markdown"},
                        timeout=15,
                    )
                    if resp.status_code != 200:
                        # Retry without Markdown (formatting errors)
                        await client.post(
                            f"{self._base}/sendMessage",
                            json={"chat_id": chat_id, "text": chunk},
                            timeout=15,
                        )
            return True
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    async def set_webhook(self, url: str, secret_token: str = "") -> bool:
        try:
            import httpx

            payload: dict = {"url": url}
            if secret_token:
                payload["secret_token"] = secret_token
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base}/setWebhook",
                    json=payload,
                    timeout=15,
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"Telegram setWebhook failed: {e}")
            return False
