import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from server.database import Base
from server.models import SystemMemory
from server.services.session_manager import SessionManager


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
