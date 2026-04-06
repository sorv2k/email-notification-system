import logging
from typing import Any, Optional

import resend

from app.core.config import settings

logger = logging.getLogger(__name__)

# Module-level client; replaced in tests via patching
resend_client: Optional[Any] = None


def get_resend_client() -> Any:
    global resend_client
    if resend_client is None:
        resend.api_key = settings.RESEND_API_KEY
        resend_client = resend.Emails
    return resend_client


async def send_email(recipient_email: str, subject: str, body: str) -> None:
    """Send an email via Resend. Raises on failure."""
    client = get_resend_client()
    params: resend.Emails.SendParams = {
        "from": settings.RESEND_FROM_EMAIL,
        "to": [recipient_email],
        "subject": subject,
        "text": body,
    }
    try:
        response = client.send(params)
        logger.info("Email sent to %s (id=%s)", recipient_email, response.get("id"))
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", recipient_email, exc)
        raise
