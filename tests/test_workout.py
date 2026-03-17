import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from server.database import Base, get_db
from server.models import Program, Workout, Exercise, SystemMemory


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
    db = TestSession()
    program = Program(name="Bench Focus", goal="315", phase="strength")
    db.add(program)
    db.commit()
    workout = Workout(
        program_id=program.id,
        date=date.today().isoformat(),
        type="strength",
        status="active",
    )
    db.add(workout)
    db.commit()
    exercise = Exercise(workout_id=workout.id, name="Bench Press", order=1)
    db.add(exercise)
    db.commit()
    db.close()
    return TestClient(app)


@pytest.fixture
def next_workout_app():
    """app with SystemMemory seeded for /workout/next tests"""
    app, TestSession = _make_app_and_session()
    return TestClient(app), TestSession


def test_get_today_workout(test_app):
    resp = test_app.get("/api/workout/today")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "active"
    assert len(data["exercises"]) == 1


def test_next_workout_no_plan(next_workout_app):
    client, _ = next_workout_app
    resp = client.get("/api/workout/next")
    assert resp.status_code == 200
    assert "No program loaded" in resp.json()["summary"]


def test_next_workout_abbreviated_day(next_workout_app):
    """abbreviated day names like Mon/Thu should match"""
    client, TestSession = next_workout_app
    db = TestSession()
    today_abbrev = date.today().strftime("%a")  # e.g. "Tue"
    plan = f"# Weekly Plan\n{today_abbrev}: Heavy Bench and Accessories\nWed: Rest Day"
    db.add(SystemMemory(key="training_plan", content=plan))
    db.commit()
    db.close()
    resp = client.get("/api/workout/next")
    data = resp.json()
    assert "Heavy Bench and Accessories" in data["summary"]


def test_next_workout_full_day_name(next_workout_app):
    """full day names like Monday should still match"""
    client, TestSession = next_workout_app
    db = TestSession()
    today_full = date.today().strftime("%A")  # e.g. "Tuesday"
    plan = f"# Schedule\n{today_full}: Upper Body Focus Session\nFriday: Lower Body"
    db.add(SystemMemory(key="training_plan", content=plan))
    db.commit()
    db.close()
    resp = client.get("/api/workout/next")
    data = resp.json()
    assert "Upper Body Focus Session" in data["summary"]


def test_next_workout_day_n_fallback(next_workout_app):
    """'Day N' patterns match based on weekday number (Mon=1)"""
    client, TestSession = next_workout_app
    db = TestSession()
    day_num = date.today().weekday() + 1  # Mon=1
    plan = f"# Program\nDay {day_num}: Squat and Deadlift Volume\nDay 7: Active Recovery"
    db.add(SystemMemory(key="training_plan", content=plan))
    db.commit()
    db.close()
    resp = client.get("/api/workout/next")
    data = resp.json()
    assert "Squat and Deadlift Volume" in data["summary"]


def test_next_workout_no_match(next_workout_app):
    """when no day matches, return helpful fallback message"""
    client, TestSession = next_workout_app
    db = TestSession()
    plan = "# Program\nSomeOtherDay: Chest and Arms"
    db.add(SystemMemory(key="training_plan", content=plan))
    db.commit()
    db.close()
    resp = client.get("/api/workout/next")
    data = resp.json()
    today_name = date.today().strftime("%A")
    assert today_name in data["summary"]
    assert "not found" in data["summary"].lower() or "Chat" in data["summary"]
