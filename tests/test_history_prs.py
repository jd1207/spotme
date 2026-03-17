import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from server.database import Base, get_db
from server.models import Program, Workout, Exercise, Set, WhoopData


def _make_app_and_session():
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
    """app with a completed workout, exercises, sets, and whoop data"""
    app, TestSession = _make_app_and_session()
    db = TestSession()
    program = Program(name="Bench Peak", goal="315", phase="strength")
    db.add(program)
    db.commit()
    workout = Workout(
        program_id=program.id,
        date=date.today().isoformat(),
        type="strength",
        status="completed",
        duration=55,
    )
    db.add(workout)
    db.commit()
    bench = Exercise(workout_id=workout.id, name="Bench Press", order=1)
    squat = Exercise(workout_id=workout.id, name="Squat", order=2)
    db.add_all([bench, squat])
    db.commit()
    db.add(Set(exercise_id=bench.id, weight=225, reps=5, rpe=7.5, completed=True))
    db.add(Set(exercise_id=bench.id, weight=235, reps=3, rpe=8.5, completed=True))
    db.add(Set(exercise_id=squat.id, weight=315, reps=5, rpe=8.0, completed=True))
    # incomplete set should not appear
    db.add(Set(exercise_id=squat.id, weight=135, reps=5, rpe=3.0, completed=False))
    db.commit()
    db.add(WhoopData(
        date=date.today().isoformat(),
        recovery_score=72.0,
        hrv=65.0,
        resting_hr=52,
    ))
    db.commit()
    db.close()
    return TestClient(app)


@pytest.fixture
def empty_app():
    app, _ = _make_app_and_session()
    return TestClient(app)


# -- /workout/recent tests --

def test_recent_includes_exercises_and_recovery(seeded_app):
    resp = seeded_app.get("/api/workout/recent")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    w = data[0]
    assert w["date"] == date.today().isoformat()
    assert w["duration"] == 55
    assert w["recovery"] == 72.0
    # exercises should only include completed sets
    assert len(w["exercises"]) == 2
    bench = next(e for e in w["exercises"] if e["name"] == "Bench Press")
    assert len(bench["sets"]) == 2
    assert bench["sets"][0]["weight"] == 225
    squat = next(e for e in w["exercises"] if e["name"] == "Squat")
    assert len(squat["sets"]) == 1  # only completed set


def test_recent_no_whoop_returns_null_recovery(empty_app):
    resp = empty_app.get("/api/workout/recent")
    assert resp.status_code == 200
    assert resp.json() == []


# -- /progress/prs tests --

def test_prs_calculates_epley(seeded_app):
    resp = seeded_app.get("/api/progress/prs")
    assert resp.status_code == 200
    prs = resp.json()["prs"]
    assert len(prs) == 2
    # squat 315x5 = 315*(1+5/30) = 315*1.1667 = 367.5
    squat_pr = next(p for p in prs if p["exercise"] == "Squat")
    assert squat_pr["e1rm"] == 367.5
    assert squat_pr["weight"] == 315
    assert squat_pr["reps"] == 5
    # bench best e1rm: 235x3 = 235*(1+3/30) = 235*1.1 = 258.5
    # vs 225x5 = 225*(1+5/30) = 225*1.1667 = 262.5
    bench_pr = next(p for p in prs if p["exercise"] == "Bench Press")
    assert bench_pr["e1rm"] == 262.5
    assert bench_pr["weight"] == 225
    assert bench_pr["reps"] == 5
    # sorted by e1rm descending
    assert prs[0]["e1rm"] >= prs[1]["e1rm"]


def test_prs_empty_database(empty_app):
    resp = empty_app.get("/api/progress/prs")
    assert resp.status_code == 200
    assert resp.json()["prs"] == []
