import json
import logging
import os
import uuid
from datetime import datetime, timedelta

from server.config import TIMEZONE, SESSION_ROLLOVER_HOUR
from server.models import SystemMemory

logger = logging.getLogger(__name__)


def session_date(now: datetime | None = None) -> str:
    """return the effective session date, treating hours before SESSION_ROLLOVER_HOUR as previous day"""
    if now is None:
        now = datetime.now(TIMEZONE)
    if now.hour < SESSION_ROLLOVER_HOUR:
        now = now - timedelta(days=1)
    return now.strftime("%Y-%m-%d")

SESSION_KEY = "active_session"
SESSIONS_DIR = os.path.expanduser("~/.claude/projects/-home-deck-spotme")


class SessionManager:

    def get_or_create_session_id(self, db, today: str) -> str:
        row = db.query(SystemMemory).filter_by(key=SESSION_KEY).first()
        if row and row.content:
            data = json.loads(row.content)
            if data.get("date") == today:
                return data["session_id"]
            # new day — overwrite db row (caller handles file cleanup via invalidate_session)

        new_id = str(uuid.uuid4())
        payload = json.dumps({"session_id": new_id, "date": today})
        if row:
            row.content = payload
        else:
            db.add(SystemMemory(key=SESSION_KEY, content=payload))
        db.commit()
        return new_id

    def is_first_message(self, db, today: str) -> bool:
        row = db.query(SystemMemory).filter_by(key=SESSION_KEY).first()
        if not row or not row.content:
            return True
        data = json.loads(row.content)
        return data.get("date") != today

    def needs_handoff(self, db, today: str) -> bool:
        row = db.query(SystemMemory).filter_by(key=SESSION_KEY).first()
        if not row or not row.content:
            return False
        data = json.loads(row.content)
        return data.get("date") != today and data.get("session_id") is not None

    def get_old_session(self, db) -> tuple[str | None, str | None]:
        """return (session_id, date) of the old session, or (None, None)"""
        row = db.query(SystemMemory).filter_by(key=SESSION_KEY).first()
        if not row or not row.content:
            return None, None
        data = json.loads(row.content)
        return data.get("session_id"), data.get("date")

    def invalidate_session(self, db):
        row = db.query(SystemMemory).filter_by(key=SESSION_KEY).first()
        if row:
            if row.content:
                data = json.loads(row.content)
                self._delete_session_file(data.get("session_id"))
            db.delete(row)
            db.commit()

    def _delete_session_file(self, session_id: str | None):
        if not session_id:
            return
        path = os.path.join(SESSIONS_DIR, f"{session_id}.jsonl")
        try:
            os.remove(path)
            logger.info("deleted session file: %s", path)
        except FileNotFoundError:
            pass
