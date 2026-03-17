from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from server.database import Base, get_db
from server.models import WhoopData, SystemMemory
import pytest


def _make_app_and_session():
    """shared setup for test fixtures"""
    from server.main import create_app
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    def override_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_db
    return app, TestSession


@pytest.fixture
def test_app():
    app, TestSession = _make_app_and_session()
    return TestClient(app), TestSession


def test_morning_no_data(test_app):
    client, _ = test_app
    resp = client.get("/api/morning")
    assert resp.status_code == 200
    data = resp.json()
    assert data["zone"] == "UNKNOWN"
    assert data["plan"] == "Rest day"
    assert "No Whoop data" in data["coaching"]


def test_morning_green_recovery(test_app):
    client, TestSession = test_app
    db = TestSession()
    db.add(WhoopData(
        date=date.today().isoformat(),
        recovery_score=75.0,
        hrv=65.0,
        resting_hr=55,
    ))
    db.commit()
    db.close()

    resp = client.get("/api/morning")
    data = resp.json()
    assert data["zone"] == "GREEN"
    assert data["recovery"] == 75.0
    assert "Push it" in data["coaching"]


def test_morning_yellow_recovery(test_app):
    client, TestSession = test_app
    db = TestSession()
    db.add(WhoopData(
        date=date.today().isoformat(),
        recovery_score=50.0,
        hrv=40.0,
        resting_hr=60,
    ))
    db.commit()
    db.close()

    resp = client.get("/api/morning")
    data = resp.json()
    assert data["zone"] == "YELLOW"
    assert "dial back" in data["coaching"]


def test_morning_red_recovery(test_app):
    client, TestSession = test_app
    db = TestSession()
    db.add(WhoopData(
        date=date.today().isoformat(),
        recovery_score=20.0,
        hrv=25.0,
        resting_hr=70,
    ))
    db.commit()
    db.close()

    resp = client.get("/api/morning")
    data = resp.json()
    assert data["zone"] == "RED"
    assert "deload" in data["coaching"]


def test_morning_with_plan(test_app):
    client, TestSession = test_app
    db = TestSession()
    day_abbrev = date.today().strftime("%a")
    db.add(SystemMemory(
        key="training_plan",
        content=f"{day_abbrev}: Bench 5x5, Incline 4x8",
    ))
    db.commit()
    db.close()

    resp = client.get("/api/morning")
    data = resp.json()
    assert "Bench" in data["plan"]


def test_morning_returns_date(test_app):
    client, _ = test_app
    resp = client.get("/api/morning")
    data = resp.json()
    assert data["date"] == date.today().isoformat()
    assert data["day"] == date.today().strftime("%A")
