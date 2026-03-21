import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from server.database import Base, get_db
import server.models  # ensure all models are registered before create_all


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def db(engine):
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def test_app(engine):
    from server.main import create_app
    TestSession = sessionmaker(bind=engine)
    def override_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()
    app = create_app()
    app.dependency_overrides[get_db] = override_db
    from fastapi.testclient import TestClient
    return TestClient(app)


def test_context_includes_training_log():
    """assemble_context includes recent training log entries."""
    from server.services.claude_service import assemble_context

    context = assemble_context(
        None, None, None, [],
        memory="## Week 1\n- Heavy Bench: 255x3",
        training_log=[
            {"date": "2026-03-21", "type": "completion", "content": "Pull / Back: 75 min"},
            {"date": "2026-03-21", "type": "note", "content": "265x4 felt easy"},
        ],
    )

    assert "TRAINING LOG" in context
    assert "Pull / Back" in context
    assert "265x4 felt easy" in context
    assert "TRAINING MEMORY" in context or "Week 1" in context


def test_training_log_model(db):
    """TrainingLog model stores structured workout events."""
    from server.models import TrainingLog
    db.add(TrainingLog(
        date="2026-03-21",
        log_type="completion",
        content='{"day": "Pull / Back", "duration": 75, "exercises": ["Pull-ups 5x8", "Barbell Row 4x6"]}',
    ))
    db.add(TrainingLog(
        date="2026-03-21",
        log_type="note",
        content="265x4 felt easy on green recovery, bump to 275 next week",
    ))
    db.commit()
    logs = db.query(TrainingLog).all()
    assert len(logs) == 2
    assert logs[0].log_type == "completion"
    assert logs[1].log_type == "note"


def test_chat_saves_training_log_entry(test_app, engine):
    """Chat route saves training_log_entry from Claude response."""
    from server.models import TrainingLog

    TestSession = sessionmaker(bind=engine)

    with patch("server.routes.chat.ClaudeService") as MockService:
        mock_instance = MagicMock()
        MockService.return_value = mock_instance
        mock_instance.chat = AsyncMock(return_value={
            "response": "Nice work on pull day!",
            "layout": None,
            "profile": None,
            "memory_update": None,
            "set_suggestion": None,
            "meal": None,
            "workout_plan": None,
            "training_log_entry": {
                "type": "completion",
                "day": "Pull / Back",
                "summary": "75 min, all exercises completed",
            },
        })

        resp = test_app.post("/api/chat", json={"message": "just finished pull day"})

    assert resp.status_code == 200

    session = TestSession()
    log = session.query(TrainingLog).first()
    assert log is not None
    assert log.log_type == "completion"
    assert "Pull / Back" in log.content
    session.close()


def test_memory_update_blocked_when_log_entry_present(test_app, engine):
    """memory_update is ignored when training_log_entry is also present."""
    from server.models import SystemMemory

    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    session.add(SystemMemory(key="training_plan", content="Original detailed program with 5 weeks of exercises"))
    session.commit()
    session.close()

    with patch("server.routes.chat.ClaudeService") as MockService:
        mock_instance = MagicMock()
        MockService.return_value = mock_instance
        mock_instance.chat = AsyncMock(return_value={
            "response": "Workout logged!",
            "layout": None, "profile": None,
            "memory_update": "Shortened program",
            "set_suggestion": None, "meal": None, "workout_plan": None,
            "training_log_entry": {"type": "completion", "day": "Bench", "summary": "done"},
        })
        resp = test_app.post("/api/chat", json={"message": "finished bench"})

    assert resp.status_code == 200
    session = TestSession()
    mem = session.query(SystemMemory).filter_by(key="training_plan").first()
    assert mem.content == "Original detailed program with 5 weeks of exercises"
    session.close()
