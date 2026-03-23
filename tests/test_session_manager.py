import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from server.database import Base
from server.config import TIMEZONE
from server.models import SystemMemory
from server.services.session_manager import SessionManager, session_date


def _make_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_get_session_creates_new_when_none_exists():
    db = _make_db()
    mgr = SessionManager()
    session_id = mgr.get_or_create_session_id(db, "2026-03-23")
    assert session_id is not None
    row = db.query(SystemMemory).filter_by(key="active_session").first()
    assert row is not None
    data = json.loads(row.content)
    assert data["session_id"] == session_id
    assert data["date"] == "2026-03-23"


def test_get_session_reuses_existing_same_day():
    db = _make_db()
    mgr = SessionManager()
    id1 = mgr.get_or_create_session_id(db, "2026-03-23")
    id2 = mgr.get_or_create_session_id(db, "2026-03-23")
    assert id1 == id2


def test_get_session_creates_new_on_new_day():
    db = _make_db()
    mgr = SessionManager()
    old_id = mgr.get_or_create_session_id(db, "2026-03-22")
    new_id = mgr.get_or_create_session_id(db, "2026-03-23")
    assert old_id != new_id
    row = db.query(SystemMemory).filter_by(key="active_session").first()
    data = json.loads(row.content)
    assert data["date"] == "2026-03-23"


def test_is_first_message_of_day():
    db = _make_db()
    mgr = SessionManager()
    assert mgr.is_first_message(db, "2026-03-23") is True
    mgr.get_or_create_session_id(db, "2026-03-23")
    assert mgr.is_first_message(db, "2026-03-23") is False


def test_needs_handoff():
    db = _make_db()
    mgr = SessionManager()
    mgr.get_or_create_session_id(db, "2026-03-22")
    assert mgr.needs_handoff(db, "2026-03-23") is True
    assert mgr.needs_handoff(db, "2026-03-22") is False


def test_invalidate_session():
    db = _make_db()
    mgr = SessionManager()
    mgr.get_or_create_session_id(db, "2026-03-23")
    mgr.invalidate_session(db)
    assert mgr.is_first_message(db, "2026-03-23") is True


def test_session_date_before_rollover_returns_yesterday():
    fake_now = datetime(2026, 3, 23, 3, 0, tzinfo=TIMEZONE)
    assert session_date(now=fake_now) == "2026-03-22"


def test_session_date_after_rollover_returns_today():
    fake_now = datetime(2026, 3, 23, 5, 0, tzinfo=TIMEZONE)
    assert session_date(now=fake_now) == "2026-03-23"


def test_session_date_at_exactly_rollover_returns_today():
    fake_now = datetime(2026, 3, 23, 4, 0, tzinfo=TIMEZONE)
    assert session_date(now=fake_now) == "2026-03-23"


def test_session_date_at_midnight_returns_yesterday():
    fake_now = datetime(2026, 3, 23, 0, 0, tzinfo=TIMEZONE)
    assert session_date(now=fake_now) == "2026-03-22"
