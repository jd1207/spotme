import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from server.database import Base, get_db
from server.models import Program, Workout, Exercise, Set, WhoopData, WhoopSyncQueue, Meal, ExerciseCatalog, WhoopToken


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def db(engine):
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    yield session
    session.close()


@pytest.fixture
def seeded_db(db):
    program = Program(name="Test", goal="test", phase="test")
    db.add(program)
    db.commit()
    workout = Workout(
        program_id=program.id, date="2026-03-16",
        type="strength", status="completed", duration=45,
    )
    db.add(workout)
    db.commit()
    exercise = Exercise(workout_id=workout.id, name="Bench Press", order=1)
    db.add(exercise)
    db.commit()
    db.add(Set(exercise_id=exercise.id, weight=225, reps=5, rpe=7.5, completed=True))
    db.add(Set(exercise_id=exercise.id, weight=225, reps=5, rpe=8.0, completed=True))
    db.commit()
    return db


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
    return TestClient(app)


# -- sync_whoop_biometrics tests --

@pytest.mark.asyncio
async def test_sync_biometrics_happy_path(db):
    from server.services.whoop_service import sync_whoop_biometrics

    mock_recovery = MagicMock()
    mock_recovery.created_at = "2026-03-16T10:00:00Z"
    mock_recovery.recovery_score = 85.0
    mock_recovery.hrv = 72.5
    mock_recovery.resting_hr = 50

    mock_sleep = MagicMock()
    mock_sleep.created_at = "2026-03-16T06:00:00Z"
    mock_sleep.performance = 90.0
    mock_sleep.total_in_bed_hours = 7.8

    mock_cycle = MagicMock()
    mock_cycle.start = "2026-03-16T00:00:00Z"
    mock_cycle.strain = 12.5

    mock_client = AsyncMock()
    mock_client.get_recovery.return_value = [mock_recovery]
    mock_client.get_sleep.return_value = [mock_sleep]
    mock_client.get_cycles.return_value = [mock_cycle]

    with patch("server.services.whoop_service.get_whoop_client") as mock_factory:
        mock_factory.return_value = mock_client
        result = await sync_whoop_biometrics(db, force=True)

    assert result["synced"] == 1

    whoop = db.query(WhoopData).filter_by(date="2026-03-16").first()
    assert whoop.recovery_score == 85.0
    assert whoop.hrv == 72.5
    assert whoop.sleep_score == 90.0
    assert whoop.sleep_duration == 7.8
    assert whoop.strain == 12.5


@pytest.mark.asyncio
async def test_sync_biometrics_api_error(db):
    from server.services.whoop_service import sync_whoop_biometrics

    mock_client = AsyncMock()
    from whoop import WhoopAPIError
    mock_client.get_recovery.side_effect = WhoopAPIError("endpoint moved", status_code=404)

    with patch("server.services.whoop_service.get_whoop_client") as mock_factory:
        mock_factory.return_value = mock_client
        result = await sync_whoop_biometrics(db, force=True)

    assert result["synced"] == 0
    assert "endpoint moved" in result["error"]


@pytest.mark.asyncio
async def test_sync_biometrics_skips_duplicates(db):
    from server.services.whoop_service import sync_whoop_biometrics

    db.add(WhoopData(date="2026-03-16", recovery_score=80.0, hrv=60.0, resting_hr=55))
    db.commit()

    mock_recovery = MagicMock()
    mock_recovery.created_at = "2026-03-16T10:00:00Z"
    mock_recovery.recovery_score = 85.0
    mock_recovery.hrv = 72.5
    mock_recovery.resting_hr = 50

    mock_client = AsyncMock()
    mock_client.get_recovery.return_value = [mock_recovery]
    mock_client.get_sleep.return_value = []
    mock_client.get_cycles.return_value = []

    with patch("server.services.whoop_service.get_whoop_client") as mock_factory:
        mock_factory.return_value = mock_client
        result = await sync_whoop_biometrics(db, force=True)

    assert result["synced"] == 0

    whoop = db.query(WhoopData).filter_by(date="2026-03-16").first()
    assert whoop.recovery_score == 80.0  # unchanged


# -- push_workout_to_whoop tests --

@pytest.mark.asyncio
async def test_push_workout_happy_path(seeded_db):
    from server.services.whoop_service import push_workout_to_whoop

    mock_activity = MagicMock()
    mock_activity.id = 12345

    mock_client = AsyncMock()
    mock_client.create_activity.return_value = mock_activity

    workout = seeded_db.query(Workout).first()
    with patch("server.services.whoop_service.get_whoop_client") as mock_factory:
        mock_factory.return_value = mock_client
        result = await push_workout_to_whoop(seeded_db, workout.id)

    assert result["synced"] is True
    assert result["activity_id"] == 12345
    mock_client.create_activity.assert_called_once()
    mock_client.link_exercises_detailed.assert_called_once()


@pytest.mark.asyncio
async def test_push_workout_queues_on_failure(seeded_db):
    from server.services.whoop_service import push_workout_to_whoop

    mock_client = AsyncMock()
    mock_client.create_activity.side_effect = Exception("server error")

    workout = seeded_db.query(Workout).first()
    with patch("server.services.whoop_service.get_whoop_client") as mock_factory:
        mock_factory.return_value = mock_client
        result = await push_workout_to_whoop(seeded_db, workout.id)

    assert result["synced"] is False
    assert result["queued"] is True

    queued = seeded_db.query(WhoopSyncQueue).first()
    assert queued is not None
    assert queued.workout_id == workout.id
    assert queued.status == "pending"


@pytest.mark.asyncio
async def test_push_workout_not_found(db):
    from server.services.whoop_service import push_workout_to_whoop

    result = await push_workout_to_whoop(db, 9999)
    assert result["synced"] is False
    assert "not found" in result["error"]


# -- process_whoop_queue tests --

@pytest.mark.asyncio
async def test_queue_retry_success(seeded_db):
    from server.services.whoop_service import process_whoop_queue
    from datetime import datetime, timedelta

    seeded_db.add(WhoopToken(
        access_token="fake-token", refresh_token="fake-refresh",
        expires_at=datetime.utcnow() + timedelta(hours=1),
    ))
    workout = seeded_db.query(Workout).first()
    seeded_db.add(WhoopSyncQueue(
        workout_id=workout.id,
        payload='{"date": "2026-03-16"}',
        status="pending",
        retries=1,
    ))
    seeded_db.commit()

    from whoop import WorkoutResult
    mock_client = AsyncMock()
    mock_client.log_workout.return_value = WorkoutResult(activity_id=999, exercises_linked=False)

    with patch("server.services.whoop_service.get_whoop_client", return_value=mock_client):
        result = await process_whoop_queue(seeded_db)

    assert result["processed"] == 1
    item = seeded_db.query(WhoopSyncQueue).first()
    assert item.status == "synced"


@pytest.mark.asyncio
async def test_queue_retry_marks_failed_after_max(seeded_db):
    from server.services.whoop_service import process_whoop_queue
    from whoop import WhoopAPIError
    from datetime import datetime, timedelta

    seeded_db.add(WhoopToken(
        access_token="fake-token", refresh_token="fake-refresh",
        expires_at=datetime.utcnow() + timedelta(hours=1),
    ))
    workout = seeded_db.query(Workout).first()
    seeded_db.add(WhoopSyncQueue(
        workout_id=workout.id,
        payload='{"date": "2026-03-16"}',
        status="pending",
        retries=2,  # one more attempt before max
    ))
    seeded_db.commit()

    mock_client = AsyncMock()
    mock_client.log_workout.side_effect = WhoopAPIError("still broken", status_code=500)

    with patch("server.services.whoop_service.get_whoop_client", return_value=mock_client):
        result = await process_whoop_queue(seeded_db)

    assert result["processed"] == 0
    item = seeded_db.query(WhoopSyncQueue).first()
    assert item.status == "failed"
    assert item.retries == 3


@pytest.mark.asyncio
async def test_queue_empty_noop(db):
    from server.services.whoop_service import process_whoop_queue
    from datetime import datetime, timedelta

    # add token so guard passes, but no pending items
    db.add(WhoopToken(
        access_token="fake-token", refresh_token="fake-refresh",
        expires_at=datetime.utcnow() + timedelta(hours=1),
    ))
    db.commit()

    result = await process_whoop_queue(db)

    assert result["processed"] == 0


# -- route tests --

def test_whoop_sync_no_token(test_app):
    # no WhoopToken in db — sync should report not connected
    resp = test_app.get("/api/whoop/sync")
    assert resp.status_code == 200
    assert "not co" in resp.json()["error"]


def test_whoop_retry_no_token(test_app):
    # no WhoopToken in db — retry should report not connected
    resp = test_app.post("/api/whoop/retry")
    assert resp.status_code == 200
    assert "not co" in resp.json()["error"]


def test_complete_workout_no_whoop(test_app, engine):
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    from datetime import date
    program = Program(name="T", goal="t", phase="t")
    session.add(program)
    session.commit()
    workout = Workout(
        program_id=program.id, date=date.today().isoformat(),
        type="strength", status="active",
    )
    session.add(workout)
    session.commit()
    workout_id = workout.id
    session.close()

    # no WhoopToken row in db — whoop not configured
    resp = test_app.post("/api/workout/complete", json={"workout_id": workout_id})

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["whoop_synced"] is False
    assert data["whoop_error"] == "whoop not configured"


def test_get_whoop_client_from_db_token(db):
    """get_whoop_client loads tokens from WhoopToken table."""
    from datetime import datetime, timedelta

    db.add(WhoopToken(
        access_token="test-access",
        refresh_token="test-refresh",
        expires_at=datetime.utcnow() + timedelta(hours=1),
    ))
    db.commit()

    with patch("whoop.WhoopClient") as MockClient:
        from server.services.whoop_service import get_whoop_client
        client = get_whoop_client(db)
        MockClient.assert_called_once()


def test_get_whoop_client_no_token(db):
    """get_whoop_client raises when no token stored."""
    from server.services.whoop_service import get_whoop_client
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        get_whoop_client(db)



# -- /api/whoop/latest tests --

def test_whoop_latest_no_data(test_app):
    resp = test_app.get("/api/whoop/latest")
    assert resp.status_code == 200
    assert resp.json()["data"] is None


def test_whoop_latest_with_data(test_app, engine):
    from datetime import date
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    session.add(WhoopData(
        date=date.today().isoformat(),
        recovery_score=85.0, hrv=72.5, resting_hr=50,
        sleep_score=90.0, sleep_duration=7.8, strain=12.5,
    ))
    session.commit()
    session.close()

    resp = test_app.get("/api/whoop/latest")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["recovery_score"] == 85.0
    assert data["strain"] == 12.5



@pytest.mark.asyncio
async def test_sync_biometrics_cycles_fail_graceful(db):
    from server.services.whoop_service import sync_whoop_biometrics
    from whoop import WhoopAPIError

    mock_recovery = MagicMock()
    mock_recovery.created_at = "2026-03-17T10:00:00Z"
    mock_recovery.recovery_score = 80.0
    mock_recovery.hrv = 65.0
    mock_recovery.resting_hr = 52

    mock_client = AsyncMock()
    mock_client.get_recovery.return_value = [mock_recovery]
    mock_client.get_sleep.return_value = []
    mock_client.get_cycles.side_effect = WhoopAPIError("authorization was not valid", status_code=401)

    with patch("server.services.whoop_service.get_whoop_client") as mock_factory:
        mock_factory.return_value = mock_client
        result = await sync_whoop_biometrics(db, force=True)

    assert result["synced"] == 1
    assert "strain unavailable" in result["warnings"][0]

    whoop = db.query(WhoopData).filter_by(date="2026-03-17").first()
    assert whoop.recovery_score == 80.0


@pytest.mark.asyncio
async def test_sync_skips_when_fresh(db):
    """sync_whoop_biometrics skips if data is less than 2 hours old."""
    from datetime import timedelta
    from server.config import today_eastern

    db.add(WhoopData(
        date=today_eastern(),
        recovery_score=78.0,
        synced_at=datetime.utcnow() - timedelta(minutes=30),
    ))
    db.commit()

    from server.services.whoop_service import sync_whoop_biometrics
    result = await sync_whoop_biometrics(db, force=False)
    assert result["skipped"] is True


@pytest.mark.asyncio
async def test_populate_exercise_catalog(db):
    """Fetching exercise catalog populates ExerciseCatalog table."""
    from server.models import ExerciseCatalog, WhoopToken
    from datetime import datetime, timedelta

    # need a token for get_whoop_client
    db.add(WhoopToken(
        access_token="test", refresh_token="test",
        expires_at=datetime.utcnow() + timedelta(hours=1),
    ))
    db.commit()

    ex1 = MagicMock()
    ex1.id = "BENCHPRESS_BARBELL"
    ex1.name = "Bench Press"
    ex1.equipment = "BARBELL"
    ex1.muscle_group = "CHEST"

    ex2 = MagicMock()
    ex2.id = "SQUAT_BARBELL"
    ex2.name = "Squat"
    ex2.equipment = "BARBELL"
    ex2.muscle_group = "LEGS"

    mock_catalog = MagicMock()
    mock_catalog.exercises = [ex1, ex2]

    with patch("server.services.whoop_service.get_whoop_client") as mock_factory:
        mock_client = AsyncMock()
        mock_factory.return_value = mock_client
        mock_client.get_exercises = AsyncMock(return_value=mock_catalog)

        from server.services.whoop_service import populate_exercise_catalog
        await populate_exercise_catalog(db)

    assert db.query(ExerciseCatalog).count() == 2
    bench = db.query(ExerciseCatalog).filter_by(whoop_id="BENCHPRESS_BARBELL").first()
    assert bench.name == "Bench Press"


def test_v04_schema_columns(db):
    """verify v0.4 columns exist on models"""
    ex = Exercise(name="test", whoop_exercise_id="BENCHPRESS_BARBELL", order=1)
    w = Workout(date="2026-03-18", status="active", type="strength", whoop_activity_id="uuid-123")
    m = Meal(date="2026-03-18", description="test", journal_signals='{"caffeine": 1}')
    sq = WhoopSyncQueue(sync_type="journal", status="pending", payload="{}")
    ec = ExerciseCatalog(whoop_id="BENCHPRESS_BARBELL", name="Bench Press")
    db.add_all([ex, w, m, sq, ec])
    db.commit()
    assert ex.whoop_exercise_id == "BENCHPRESS_BARBELL"
    assert w.whoop_activity_id == "uuid-123"
    assert ec.name == "Bench Press"
    assert sq.sync_type == "journal"
    assert m.journal_signals == '{"caffeine": 1}'
