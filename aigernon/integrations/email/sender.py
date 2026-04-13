"""Resend email sender."""

from typing import Optional
from loguru import logger


class EmailSender:
    """Send emails via Resend API."""

    def __init__(self, api_key: str, from_address: str = "AIGernon <onboarding@resend.dev>"):
        self.api_key = api_key
        self.from_address = from_address

    async def send(self, to: str, subject: str, text: str, html: Optional[str] = None) -> bool:
        try:
            import httpx

            payload: dict = {
                "from": self.from_address,
                "to": [to],
                "subject": subject,
                "text": text,
            }
            if html:
                payload["html"] = html

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                    timeout=15,
                )
                if resp.status_code not in (200, 201):
                    logger.warning(f"Resend error {resp.status_code}: {resp.text}")
                    return False
                return True
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False
