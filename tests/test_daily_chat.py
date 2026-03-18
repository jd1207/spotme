import pytest
from datetime import timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from server.database import Base, get_db
from server.config import today_eastern
from server.models import Conversation, Workout, WhoopData, Meal


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    session = sessionmaker(bind=eng)()
    yield session
    session.close()


@pytest.fixture
def client(db):
    from server.main import create_app
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _yesterday() -> str:
    from datetime import datetime
    from server.config import TIMEZONE
    return (datetime.now(TIMEZONE).date() - timedelta(days=1)).isoformat()


def test_chat_days_empty(client):
    resp = client.get("/api/chat/days")
    assert resp.status_code == 200
    assert resp.json()["days"] == []


def test_chat_days_with_messages(db, client):
    today = today_eastern()
    db.add(Conversation(role="user", content="hello", date=today))
    db.add(Conversation(role="assistant", content="hi", date=today))
    db.commit()
    resp = client.get("/api/chat/days")
    days = resp.json()["days"]
    assert len(days) == 1
    assert days[0]["date"] == today
    assert days[0]["message_count"] == 2


def test_chat_days_multiple_dates(db, client):
    today = today_eastern()
    yesterday = _yesterday()
    db.add(Conversation(role="user", content="msg1", date=today))
    db.add(Conversation(role="user", content="msg2", date=yesterday))
    db.commit()
    resp = client.get("/api/chat/days")
    days = resp.json()["days"]
    assert len(days) == 2
    assert days[0]["date"] == today


def test_chat_days_includes_workout_type(db, client):
    today = today_eastern()
    db.add(Workout(date=today, type="strength", status="active"))
    db.add(Conversation(role="user", content="hello", date=today))
    db.commit()
    resp = client.get("/api/chat/days")
    days = resp.json()["days"]
    assert days[0]["workout_type"] == "strength"


def test_chat_days_includes_recovery(db, client):
    today = today_eastern()
    db.add(WhoopData(date=today, recovery_score=79.0, hrv=65.0, resting_hr=55))
    db.add(Conversation(role="user", content="hello", date=today))
    db.commit()
    resp = client.get("/api/chat/days")
    days = resp.json()["days"]
    assert days[0]["recovery_score"] == 79.0
    assert days[0]["recovery_zone"] == "GREEN"


def test_chat_day_returns_messages(db, client):
    today = today_eastern()
    db.add(Conversation(role="user", content="first", date=today))
    db.add(Conversation(role="assistant", content="second", date=today))
    db.commit()
    resp = client.get(f"/api/chat/day/{today}")
    messages = resp.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["content"] == "first"
    assert messages[1]["content"] == "second"


def test_chat_day_empty_date(client):
    resp = client.get("/api/chat/day/2020-01-01")
    assert resp.json()["messages"] == []
