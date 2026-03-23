import json
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from server.database import Base, get_db
from server.models import SystemMemory, UserProfile, Conversation
from server.config import today_eastern


def _make_app():
    from server.main import create_app
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    def override():
        db = TestSession()
        try: yield db
        finally: db.close()
    app = create_app()
    app.dependency_overrides[get_db] = override
    return TestClient(app), TestSession


def test_chat_creates_session_on_first_message():
    client, TestSession = _make_app()
    db = TestSession()
    db.add(UserProfile(name="Test"))
    db.commit()
    db.close()

    mock_response = json.dumps({"response": "Hey! Ready to train.", "layout": None})
    with patch("server.services.claude_service._call_claude_session", new_callable=AsyncMock, return_value=mock_response):
        resp = client.post("/api/chat", json={"message": "hi", "workout_id": None, "date": None})
    assert resp.status_code == 200
    assert "Ready to train" in resp.json()["response"]

    db = TestSession()
    session_row = db.query(SystemMemory).filter_by(key="active_session").first()
    assert session_row is not None
    data = json.loads(session_row.content)
    assert data["date"] == today_eastern()
    db.close()


def test_chat_resumes_existing_session():
    client, TestSession = _make_app()
    db = TestSession()
    db.add(UserProfile(name="Test"))
    db.add(SystemMemory(key="active_session", content=json.dumps({"session_id": "existing-uuid", "date": today_eastern()})))
    db.commit()
    db.close()

    mock_response = json.dumps({"response": "Welcome back.", "layout": None})
    with patch("server.services.claude_service._call_claude_session", new_callable=AsyncMock, return_value=mock_response) as mock_call:
        resp = client.post("/api/chat", json={"message": "hey", "workout_id": None, "date": None})
    assert resp.status_code == 200
    # check that it used resume (is_first=False)
    call_kwargs = mock_call.call_args
    assert call_kwargs.kwargs.get("is_first") is False or (len(call_kwargs.args) > 2 and call_kwargs.args[2] is False)


def test_memory_update_allowed_with_training_log():
    """memory_update should no longer be blocked when training_log_entry is present"""
    client, TestSession = _make_app()
    db = TestSession()
    db.add(UserProfile(name="Test"))
    db.add(SystemMemory(key="training_plan", content="original program text that is long enough"))
    db.commit()
    db.close()

    mock_response = json.dumps({
        "response": "Updated your program and logged the completion.",
        "layout": None,
        "memory_update": "updated program text that is about the same length as before",
        "training_log_entry": {"type": "completion", "day": "Heavy Bench", "summary": "265x4"},
    })
    with patch("server.services.claude_service._call_claude_session", new_callable=AsyncMock, return_value=mock_response):
        resp = client.post("/api/chat", json={"message": "update program", "workout_id": None, "date": None})
    assert resp.status_code == 200

    db = TestSession()
    mem = db.query(SystemMemory).filter_by(key="training_plan").first()
    assert mem.content == "updated program text that is about the same length as before"
    db.close()


def test_memory_update_blocked_if_truncated():
    """memory_update should be blocked if >50% shorter than existing"""
    client, TestSession = _make_app()
    db = TestSession()
    db.add(UserProfile(name="Test"))
    db.add(SystemMemory(key="training_plan", content="a" * 1000))
    db.commit()
    db.close()

    mock_response = json.dumps({
        "response": "Here's the update.",
        "layout": None,
        "memory_update": "short",
    })
    with patch("server.services.claude_service._call_claude_session", new_callable=AsyncMock, return_value=mock_response):
        resp = client.post("/api/chat", json={"message": "update", "workout_id": None, "date": None})
    assert resp.status_code == 200

    db = TestSession()
    mem = db.query(SystemMemory).filter_by(key="training_plan").first()
    assert mem.content == "a" * 1000  # unchanged, blocked
    db.close()
