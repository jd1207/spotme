import logging
import httpx
from server.config import settings

logger = logging.getLogger(__name__)


async def send_morning_notification(briefing: dict):
    """send push notification via ntfy.sh"""
    if not settings.ntfy_topic:
        logger.info("ntfy_topic not configured, skipping notification")
        return

    ntfy_url = f"https://ntfy.sh/{settings.ntfy_topic}"
    zone = briefing["zone"]
    recovery = briefing.get("recovery")
    plan = briefing["plan"]
    coaching = briefing["coaching"]

    title = f"SpotMe -- {briefing['day']} [{zone}]"
    recovery_str = f"Recovery {round(recovery)}%" if recovery else "No Whoop data"
    body = f"{recovery_str}\n{plan}\n{coaching}"

    try:
        async with httpx.AsyncClient() as client:
            await client.post(ntfy_url, content=body.encode(), headers={
                "Title": title,
                "Priority": "3" if zone == "RED" else "default",
                "Tags": "muscle" if zone == "GREEN" else "warning" if zone == "YELLOW" else "sleeping",
            })
        logger.info("morning notification sent")
    except Exception as e:
        logger.warning("morning notification failed: %s", e)
