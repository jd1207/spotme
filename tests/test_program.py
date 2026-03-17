from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from server.database import Base, get_db
from server.models import SystemMemory, Program, Workout

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
### Week 3
- Heavy: 285x3, 295x2
- Volume: 240x5x4
## Pull / Back Day (Fridays)
- Pull-ups 5x5-8
- Barbell rows 4x6-8
## Leg Day (Saturdays)
- Trap bar deadlift 4x5-6
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

    # 3 weeks parsed
    assert len(data["weeks"]) == 3
    w1 = data["weeks"][0]
    assert w1["number"] == 1
    assert w1["title"] == "Week 1 (Current)"

    # each week has 4 days (Pull, Legs, Heavy, Volume)
    assert len(w1["days"]) == 4
    day_types = [d["type"] for d in w1["days"]]
    assert "Pull / Back" in day_types
    assert "Legs" in day_types
    assert "Heavy Bench" in day_types
    assert "Volume Bench" in day_types

    # heavy bench in week 1 should be completed
    heavy = next(d for d in w1["days"] if d["type"] == "Heavy Bench")
    assert heavy["status"] == "completed"
    assert "COMPLETED" in heavy["note"] or "completed" in heavy["note"].lower()

    # volume bench in week 1 should be upcoming
    volume = next(d for d in w1["days"] if d["type"] == "Volume Bench")
    assert volume["status"] == "upcoming"
    assert "235x6x4" in volume["planned"]

    # recurring templates filled in
    pull = next(d for d in w1["days"] if d["type"] == "Pull / Back")
    assert "Pull-ups" in pull["planned"]
    legs = next(d for d in w1["days"] if d["type"] == "Legs")
    assert "Trap bar deadlift" in legs["planned"]


def test_program_progression():
    app, TestSession = _make_app_and_session()
    db = TestSession()
    db.add(SystemMemory(key="training_plan", content=SAMPLE_PLAN))
    db.commit()
    db.close()

    client = TestClient(app)
    resp = client.get("/api/program")
    data = resp.json()

    assert len(data["progression"]) == 3
    assert data["progression"][0]["weight"] == 265
    assert data["progression"][1]["weight"] == 285
    assert data["progression"][2]["weight"] == 295


def test_program_stats():
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


def test_program_day_order():
    """days should follow Fri -> Sat -> Sun -> Tue/Wed order"""
    app, TestSession = _make_app_and_session()
    db = TestSession()
    db.add(SystemMemory(key="training_plan", content=SAMPLE_PLAN))
    db.commit()
    db.close()

    client = TestClient(app)
    resp = client.get("/api/program")
    data = resp.json()

    w1 = data["weeks"][0]
    day_abbrevs = [d["day_of_week"] for d in w1["days"]]
    assert day_abbrevs == ["Fri", "Sat", "Sun", "Tue/Wed"]


def test_program_progression_picks_max():
    """progression should pick the heaviest weight per week"""
    plan = """## Weekly Schedule
- Sunday: Heavy Bench

## 5-Week Bench Peak Program

### Week 1
- Heavy: 225x5, 255x3, 265x2

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
