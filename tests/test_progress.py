from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server.database import Base, get_db
from server.models import Program, Workout, Exercise, Set, WhoopData


def _make_app():
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
def seeded_app():
    app, TestSession = _make_app()
    db = TestSession()

    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    program = Program(name="Test", goal="strength", phase="peak")
    db.add(program)
    db.commit()

    # yesterday workout
    w1 = Workout(
        program_id=program.id, date=yesterday,
        type="strength", status="completed",
    )
    db.add(w1)
    db.commit()
    e1 = Exercise(workout_id=w1.id, name="Bench Press", order=1)
    db.add(e1)
    db.commit()
    db.add(Set(
        exercise_id=e1.id, weight=225, reps=5,
        rpe=8.0, completed=True,
    ))
    db.commit()

    # today workout
    w2 = Workout(
        program_id=program.id, date=today,
        type="strength", status="completed",
    )
    db.add(w2)
    db.commit()
    e2 = Exercise(workout_id=w2.id, name="Squat", order=1)
    db.add(e2)
    db.commit()
    db.add(Set(
        exercise_id=e2.id, weight=315, reps=3,
        rpe=9.0, completed=True,
    ))
    # incomplete set should be excluded from e1rm but included in volume
    db.add(Set(
        exercise_id=e2.id, weight=135, reps=10,
        completed=False,
    ))
    db.commit()

    # whoop data
    db.add(WhoopData(
        date=yesterday, recovery_score=72.0,
        hrv=65.0, strain=12.5,
    ))
    db.add(WhoopData(
        date=today, recovery_score=85.0,
        hrv=70.0, strain=None,
    ))
    db.commit()
    db.close()

    return TestClient(app)


@pytest.fixture
def empty_app():
    app, _ = _make_app()
    return TestClient(app)


def test_progress_e1rm_trend(seeded_app):
    resp = seeded_app.get("/api/progress")
    assert resp.status_code == 200
    data = resp.json()

    trend = data["e1rm_trend"]
    assert len(trend) == 2

    # yesterday: bench 225x5 -> 225*(1+5/30) = 262.5
    assert trend[0]["e1rm"] == 262.5
    assert trend[0]["exercise"] == "Bench Press"

    # today: squat 315x3 -> 315*(1+3/30) = 346.5
    assert trend[1]["e1rm"] == 346.5
    assert trend[1]["exercise"] == "Squat"


def test_progress_volume_trend(seeded_app):
    resp = seeded_app.get("/api/progress")
    data = resp.json()

    vol = data["volume_trend"]
    assert len(vol) == 2
    # yesterday: 225*5 = 1125
    assert vol[0]["volume"] == 1125
    # today: only completed set 315*3 = 945
    assert vol[1]["volume"] == 945


def test_progress_whoop_trends(seeded_app):
    resp = seeded_app.get("/api/progress")
    data = resp.json()

    whoop = data["whoop"]
    assert len(whoop["recovery"]) == 2
    assert whoop["recovery"][0]["value"] == 72.0
    assert whoop["recovery"][1]["value"] == 85.0

    assert len(whoop["hrv"]) == 2
    assert whoop["hrv"][1]["value"] == 70.0

    # strain: only yesterday has a value
    assert len(whoop["strain"]) == 1
    assert whoop["strain"][0]["value"] == 12.5


def test_progress_empty_database(empty_app):
    resp = empty_app.get("/api/progress")
    assert resp.status_code == 200
    data = resp.json()
    assert data["e1rm_trend"] == []
    assert data["volume_trend"] == []
    assert data["whoop"]["recovery"] == []
    assert data["whoop"]["hrv"] == []
    assert data["whoop"]["strain"] == []


def test_progress_excludes_old_data():
    """workouts older than 30 days should not appear"""
    app, TestSession = _make_app()
    db = TestSession()

    old_date = (date.today() - timedelta(days=45)).isoformat()
    program = Program(name="Old", goal="test", phase="test")
    db.add(program)
    db.commit()
    w = Workout(
        program_id=program.id, date=old_date,
        type="strength", status="completed",
    )
    db.add(w)
    db.commit()
    e = Exercise(workout_id=w.id, name="Deadlift", order=1)
    db.add(e)
    db.commit()
    db.add(Set(
        exercise_id=e.id, weight=405, reps=3,
        completed=True,
    ))
    db.commit()
    db.close()

    client = TestClient(app)
    resp = client.get("/api/progress")
    data = resp.json()
    assert data["e1rm_trend"] == []
    assert data["volume_trend"] == []
