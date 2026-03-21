import pytest
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
