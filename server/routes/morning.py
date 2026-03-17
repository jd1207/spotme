import logging
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from server.database import get_db
from server.models import WhoopData, SystemMemory

logger = logging.getLogger(__name__)
router = APIRouter()

RECOVERY_GREEN = 67
RECOVERY_YELLOW = 34


@router.get("/morning")
async def morning_briefing(
    db: Session = Depends(get_db),
    notify: bool = Query(False),
):
    today = date.today()
    day_name = today.strftime("%A")
    day_abbrev = today.strftime("%a")

    # get today's whoop data
    whoop = db.query(WhoopData).filter_by(date=today.isoformat()).first()
    recovery = whoop.recovery_score if whoop else None
    zone = _recovery_zone(recovery)

    # get today's planned workout from training memory
    plan = _find_plan(db, day_name, day_abbrev)

    # coaching note based on recovery
    coaching = _coaching_note(zone)

    briefing = {
        "date": today.isoformat(),
        "day": day_name,
        "zone": zone,
        "recovery": recovery,
        "hrv": whoop.hrv if whoop else None,
        "sleep_score": whoop.sleep_score if whoop else None,
        "plan": plan,
        "coaching": coaching,
    }

    if notify:
        try:
            from server.services.notification_service import send_morning_notification
            await send_morning_notification(briefing)
        except Exception as e:
            logger.warning("failed to send notification: %s", e)

    return briefing


def _recovery_zone(recovery: float | None) -> str:
    if recovery is None:
        return "UNKNOWN"
    if recovery >= RECOVERY_GREEN:
        return "GREEN"
    if recovery >= RECOVERY_YELLOW:
        return "YELLOW"
    return "RED"


def _find_plan(db: Session, day_name: str, day_abbrev: str) -> str:
    memory = db.query(SystemMemory).filter_by(key="training_plan").first()
    if not memory or not memory.content:
        return "Rest day"
    for line in memory.content.split("\n"):
        lower = line.lower().strip()
        if not lower or lower.startswith("#"):
            continue
        if day_name.lower() in lower or day_abbrev.lower() in lower:
            clean = line.strip().strip("-*|").strip()
            if len(clean) > 10:
                return clean
    return "Rest day"


def _coaching_note(zone: str) -> str:
    notes = {
        "RED": "Recovery is low. Consider a deload or mobility session.",
        "YELLOW": "Moderate recovery. Train but dial back intensity by 1 RPE.",
        "GREEN": "Well recovered. Push it today.",
    }
    return notes.get(zone, "No Whoop data yet. Sync your Whoop to get recovery-based coaching.")
