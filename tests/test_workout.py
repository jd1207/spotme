import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from server.database import Base, get_db
from server.models import Program, Workout, Exercise

@pytest.fixture
def test_app():
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
    from datetime import date
    db = TestSession()
    program = Program(name="Bench Focus", goal="315", phase="strength")
    db.add(program)
    db.commit()
    workout = Workout(program_id=program.id, date=date.today().isoformat(), type="strength", status="active")
    db.add(workout)
    db.commit()
    exercise = Exercise(workout_id=workout.id, name="Bench Press", order=1)
    db.add(exercise)
    db.commit()
    db.close()
    return TestClient(app)

def test_get_today_workout(test_app):
    resp = test_app.get("/api/workout/today")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "active"
    assert len(data["exercises"]) == 1
