import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from server.database import Base, get_db
from server.models import Workout, Exercise, Set
from server.config import today_eastern


def _make_app():
    from server.main import create_app
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
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
    return TestClient(app), TestSession


def _seed_workout(session):
    """create a workout with 3 planned sets"""
    w = Workout(date=today_eastern(), type="strength", status="active")
    session.add(w)
    session.flush()
    ex = Exercise(workout_id=w.id, name="Bench Press", order=0)
    session.add(ex)
    session.flush()
    sets = []
    for i in range(3):
        s = Set(
            exercise_id=ex.id, weight=225, reps=5,
            target_weight=225, target_reps=5,
            set_type="working", order=i, status="pending", completed=False
        )
        session.add(s)
        session.flush()
        sets.append(s.id)
    session.commit()
    return w.id, sets


def test_complete_set_basic():
    client, TestSession = _make_app()
    db = TestSession()
    _, set_ids = _seed_workout(db)
    db.close()

    resp = client.post("/api/workout/complete-set", json={
        "set_id": set_ids[0],
        "actual_weight": 225,
        "actual_reps": 5,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["logged_set"]["status"] == "completed"
    assert data["next_set"] is not None
    assert data["progress"]["completed"] == 1


def test_complete_set_with_feel():
    client, TestSession = _make_app()
    db = TestSession()
    _, set_ids = _seed_workout(db)
    db.close()

    resp = client.post("/api/workout/complete-set", json={
        "set_id": set_ids[0],
        "actual_weight": 225,
        "actual_reps": 5,
        "feel": "tough",
    })
    data = resp.json()
    assert data["logged_set"]["rpe"] == 9.0


def test_complete_last_set():
    client, TestSession = _make_app()
    db = TestSession()
    _, set_ids = _seed_workout(db)
    db.close()

    for sid in set_ids:
        resp = client.post("/api/workout/complete-set", json={
            "set_id": sid,
            "actual_weight": 225,
            "actual_reps": 5,
        })
    data = resp.json()
    assert data["next_set"] is None
    assert data["progress"]["completed"] == 3


def test_complete_nonexistent_set():
    client, _ = _make_app()
    resp = client.post("/api/workout/complete-set", json={
        "set_id": 9999,
        "actual_weight": 225,
        "actual_reps": 5,
    })
    assert resp.status_code == 200
    assert "error" in resp.json()
