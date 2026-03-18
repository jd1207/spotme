import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from server.database import Base, get_db
from server.models import Workout, Exercise, Set, SystemMemory
from server.config import today_eastern


SAMPLE_PLAN = """## Weekly Schedule
- Friday: Pull / Back
- Saturday: Legs
- Sunday: Heavy Bench
- Tue or Wed: Volume Bench
## 5-Week Bench Peak Program
### Week 1 (Current)
- Heavy (Sun 3/16): 255x3, 265x4, 225x6x3. COMPLETED on 56% recovery
- Volume (Wed 3/18): 235x6x4
### Week 2
- Heavy: 265x4, 275x3, 285x2
- Volume: 235x6x4
## Pull / Back Day (Fridays)
- Pull-ups 5x5-8
- Barbell rows 4x6-8
## Leg Day (Saturdays)
- Trap bar deadlift 4x5-6
"""


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


def test_program_week_no_program():
    client, _ = _make_app()
    resp = client.get("/api/program/week/1")
    assert resp.status_code == 200
    assert resp.json()["days"] == []


def test_program_week_missing_week_number():
    client, TestSession = _make_app()
    db = TestSession()
    db.add(SystemMemory(key="training_plan", content=SAMPLE_PLAN))
    db.commit()
    db.close()
    resp = client.get("/api/program/week/99")
    assert resp.status_code == 200
    data = resp.json()
    assert data["week"] == 99
    assert data["days"] == []


def test_program_week_returns_days():
    client, TestSession = _make_app()
    db = TestSession()
    db.add(SystemMemory(key="training_plan", content=SAMPLE_PLAN))
    db.commit()
    db.close()

    resp = client.get("/api/program/week/1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["week"] == 1
    assert len(data["days"]) == 4
    day_types = [d["type"] for d in data["days"]]
    assert "Heavy Bench" in day_types
    assert "Volume Bench" in day_types
    assert "Pull / Back" in day_types
    assert "Legs" in day_types


def test_program_week_day_has_source_and_exercises_fields():
    client, TestSession = _make_app()
    db = TestSession()
    db.add(SystemMemory(key="training_plan", content=SAMPLE_PLAN))
    db.commit()
    db.close()

    resp = client.get("/api/program/week/1")
    data = resp.json()
    for day in data["days"]:
        assert "source" in day
        assert "exercises" in day
        assert "summary" in day


def test_program_week_with_logged_workout():
    client, TestSession = _make_app()
    db = TestSession()
    today = today_eastern()
    w = Workout(date=today, type="strength", status="completed")
    db.add(w)
    db.flush()
    ex = Exercise(workout_id=w.id, name="Bench Press", order=0)
    db.add(ex)
    db.flush()
    db.add(Set(exercise_id=ex.id, weight=135, reps=10, target_weight=135, target_reps=10, set_type="warmup", order=0, status="completed", completed=True))
    db.add(Set(exercise_id=ex.id, weight=235, reps=6, target_weight=235, target_reps=6, set_type="working", order=1, status="completed", completed=True, rpe=7.5))
    db.commit()
    db.close()

    # the week endpoint needs a program to know which week maps to which dates
    # for now, if no program structure exists, return logged workouts by date
    resp = client.get("/api/program/week/1")
    data = resp.json()
    # should return data (exact structure depends on implementation)
    assert resp.status_code == 200


def test_program_week_completed_day_has_logged_sets():
    client, TestSession = _make_app()
    db = TestSession()
    db.add(SystemMemory(key="training_plan", content=SAMPLE_PLAN))
    today = today_eastern()
    # create a completed "heavy bench" style workout
    w = Workout(date=today, type="heavy bench", status="completed")
    db.add(w)
    db.flush()
    ex = Exercise(workout_id=w.id, name="Bench Press", order=0)
    db.add(ex)
    db.flush()
    db.add(Set(exercise_id=ex.id, weight=135.0, reps=10, set_type="warmup", order=0, status="completed", completed=True))
    db.add(Set(exercise_id=ex.id, weight=265.0, reps=4, set_type="working", order=1, status="completed", completed=True, rpe=8.0))
    db.commit()
    db.close()

    resp = client.get("/api/program/week/1")
    assert resp.status_code == 200
    data = resp.json()
    heavy = next((d for d in data["days"] if d["type"] == "Heavy Bench"), None)
    assert heavy is not None
    assert heavy["source"] == "logged"
    assert len(heavy["exercises"]) > 0
    bench = heavy["exercises"][0]
    assert bench["name"] == "Bench Press"
    assert len(bench["sets"]) == 2
    working_set = next(s for s in bench["sets"] if s["set_type"] == "working")
    assert working_set["weight"] == 265.0
    assert working_set["rpe"] == 8.0


def test_program_week_summary_computed_for_logged_day():
    client, TestSession = _make_app()
    db = TestSession()
    db.add(SystemMemory(key="training_plan", content=SAMPLE_PLAN))
    w = Workout(date=today_eastern(), type="heavy bench", status="completed")
    db.add(w)
    db.flush()
    ex = Exercise(workout_id=w.id, name="Bench Press", order=0)
    db.add(ex)
    db.flush()
    db.add(Set(exercise_id=ex.id, weight=135.0, reps=10, set_type="warmup", order=0, status="completed", completed=True))
    db.add(Set(exercise_id=ex.id, weight=265.0, reps=4, set_type="working", order=1, status="completed", completed=True, rpe=7.0))
    db.add(Set(exercise_id=ex.id, weight=275.0, reps=2, set_type="working", order=2, status="completed", completed=True, rpe=9.0))
    db.commit()
    db.close()

    resp = client.get("/api/program/week/1")
    data = resp.json()
    heavy = next(d for d in data["days"] if d["type"] == "Heavy Bench")
    summary = heavy["summary"]
    assert summary is not None
    assert summary["total_sets"] == 3
    assert summary["top_set"] == "275.0x2"
    assert summary["avg_rpe"] == 8.0


def test_program_week_planned_day_source_is_planned():
    client, TestSession = _make_app()
    db = TestSession()
    db.add(SystemMemory(key="training_plan", content=SAMPLE_PLAN))
    db.commit()
    db.close()

    resp = client.get("/api/program/week/2")
    data = resp.json()
    for day in data["days"]:
        assert day["source"] == "planned"
        assert day["exercises"] == []
        assert day["summary"] is None
