from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from server.database import Base, get_db
from server.models import (
    SystemMemory, Program, Workout, Exercise, Set, WhoopData,
)

SAMPLE_PLAN = """# Training Plan

## Athlete Profile
- Weight: 255 lbs
- Goal: 315 bench

## 5-Week Bench Peak Program

### Week 1 (Current)
- Heavy (Sun 3/16): 255x3, 265x4, 225x6x3. COMPLETED
- Volume (Wed 3/18): 235x6x4

### Week 2
- Heavy: 265x4, 275x3, 285x2
- Volume: 235x6x4

### Week 3
- Heavy: 285x3, 295x2
- Volume: 240x5x4

## Pull / Back Day (Fridays)
Pull-ups 5x5-8, Barbell rows 4x6-8

## Leg Day (Saturdays)
Trap bar deadlift 4x5-6
"""


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


def test_program_no_plan():
    app, _ = _make_app_and_session()
    client = TestClient(app)
    resp = client.get("/api/program")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_program"] is False
    assert data["sections"] == []
    assert data["weeks"] == []
    assert data["progression"] == []


def test_program_with_plan():
    app, TestSession = _make_app_and_session()
    db = TestSession()
    db.add(SystemMemory(key="training_plan", content=SAMPLE_PLAN))
    db.commit()
    db.close()

    client = TestClient(app)
    resp = client.get("/api/program")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_program"] is True

    # sections should exclude the weeks program section
    titles = [s["title"] for s in data["sections"]]
    assert "Athlete Profile" in titles
    assert "Pull / Back Day (Fridays)" in titles
    assert "Leg Day (Saturdays)" in titles

    # weeks parsed
    assert len(data["weeks"]) == 3
    assert data["weeks"][0]["number"] == 1
    assert data["weeks"][0]["title"] == "Week 1 (Current)"
    assert len(data["weeks"][0]["items"]) == 2

    # progression extracted
    assert len(data["progression"]) == 3
    assert data["progression"][0]["weight"] == 265
    assert data["progression"][1]["weight"] == 285
    assert data["progression"][2]["weight"] == 295

    assert data["stats"]["total_workouts"] == 0
    assert data["stats"]["completed_workouts"] == 0


def test_program_with_workouts():
    app, TestSession = _make_app_and_session()
    db = TestSession()
    db.add(SystemMemory(key="training_plan", content=SAMPLE_PLAN))
    program = Program(name="Test", goal="315", phase="peak")
    db.add(program)
    db.commit()
    db.add(Workout(
        program_id=program.id, date=date.today().isoformat(),
        type="strength", status="completed", duration=45,
    ))
    db.add(Workout(
        program_id=program.id, date=date.today().isoformat(),
        type="strength", status="active",
    ))
    db.commit()
    db.close()

    client = TestClient(app)
    resp = client.get("/api/program")
    data = resp.json()
    assert data["stats"]["total_workouts"] == 2
    assert data["stats"]["completed_workouts"] == 1
    assert data["stats"]["today"] == date.today().isoformat()

    # logged workout map should have today's date
    assert date.today().isoformat() in data["logged"]


def test_program_logged_exercises():
    app, TestSession = _make_app_and_session()
    db = TestSession()
    db.add(SystemMemory(key="training_plan", content=SAMPLE_PLAN))
    program = Program(name="T", goal="315", phase="peak")
    db.add(program)
    db.commit()

    workout = Workout(
        program_id=program.id, date="2026-03-16",
        type="strength", status="completed", duration=50,
    )
    db.add(workout)
    db.commit()

    ex = Exercise(workout_id=workout.id, name="Bench Press", order=1)
    db.add(ex)
    db.commit()

    db.add(Set(exercise_id=ex.id, weight=255, reps=3, rpe=8.0, completed=True))
    db.add(Set(exercise_id=ex.id, weight=265, reps=4, rpe=9.0, completed=True))
    db.commit()
    db.close()

    client = TestClient(app)
    resp = client.get("/api/program")
    data = resp.json()

    logged = data["logged"]["2026-03-16"]
    assert logged["status"] == "completed"
    assert logged["duration"] == 50
    assert len(logged["exercises"]) == 1
    assert logged["exercises"][0]["name"] == "Bench Press"
    assert len(logged["exercises"][0]["sets"]) == 2


def test_program_whoop_data():
    app, TestSession = _make_app_and_session()
    db = TestSession()
    db.add(SystemMemory(key="training_plan", content=SAMPLE_PLAN))
    db.add(WhoopData(date="2026-03-16", recovery_score=56.0, hrv=45.0, resting_hr=52))
    db.commit()
    db.close()

    client = TestClient(app)
    resp = client.get("/api/program")
    data = resp.json()

    whoop = data["whoop"]["2026-03-16"]
    assert whoop["recovery"] == 56.0
    assert whoop["hrv"] == 45.0


def test_program_progression_picks_max():
    """progression should pick the heaviest weight per week"""
    plan = """## 5-Week Bench Peak Program

### Week 1
- Heavy: 225x5, 255x3, 265x2
- Volume: 200x8x4

### Week 2
- Heavy: 275x3, 285x1
"""
    app, TestSession = _make_app_and_session()
    db = TestSession()
    db.add(SystemMemory(key="training_plan", content=plan))
    db.commit()
    db.close()

    client = TestClient(app)
    resp = client.get("/api/program")
    data = resp.json()

    assert len(data["progression"]) == 2
    assert data["progression"][0]["weight"] == 265
    assert data["progression"][1]["weight"] == 285
