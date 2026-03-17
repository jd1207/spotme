from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from server.database import Base, get_db
from server.models import SystemMemory, Program, Workout


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
    assert resp.json()["has_program"] is False
    assert resp.json()["content"] is None
    assert resp.json()["stats"] is None


def test_program_with_plan():
    app, TestSession = _make_app_and_session()
    db = TestSession()
    db.add(SystemMemory(key="training_plan", content="## Week 1\n- Bench 5x5"))
    db.commit()
    db.close()

    client = TestClient(app)
    resp = client.get("/api/program")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_program"] is True
    assert "Week 1" in data["content"]
    assert data["stats"]["total_workouts"] == 0
    assert data["stats"]["completed_workouts"] == 0


def test_program_with_workouts():
    app, TestSession = _make_app_and_session()
    db = TestSession()
    db.add(SystemMemory(key="training_plan", content="## Week 1\n- Bench 5x5"))
    program = Program(name="Test", goal="315", phase="peak")
    db.add(program)
    db.commit()
    db.add(Workout(
        program_id=program.id, date=date.today().isoformat(),
        type="strength", status="completed",
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
