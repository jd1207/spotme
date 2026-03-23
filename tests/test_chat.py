import pytest
from datetime import date
from unittest.mock import AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from server.database import Base
from server.models import WhoopData, Workout, Exercise, Set
from server.services.claude_service import ClaudeService, assemble_context
from server.routes.chat import _get_today_whoop, _get_recent_sets


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    session = sessionmaker(bind=eng)()
    yield session
    session.close()


def test_assemble_context():
    whoop = {"recovery_score": 85.0, "hrv": 65.0, "sleep_score": 90.0, "resting_hr": 50, "sleep_duration": 7.5, "strain": 12.0}
    history = [{"role": "user", "content": "how should I warm up?"}, {"role": "assistant", "content": "start with the bar"}]
    profile = {"name": "Jordan", "goals": "strength", "experience_level": "advanced", "equipment": "full gym", "training_frequency": "4x/week", "injuries_notes": None}
    memory = "# Bench Focus Program\nGoal: 315 bench"
    context = assemble_context(None, None, whoop, history, profile=profile, memory=memory)
    assert "Jordan" in context
    assert "85.0" in context
    assert "Bench Focus" in context
    assert "how should I warm up?" in context


def test_assemble_context_missing_data():
    context = assemble_context(program=None, workout=None, whoop=None, history=[])
    assert "no user profile" in context.lower()


def test_assemble_context_with_profile():
    profile = {"name": "Jordan", "goals": "strength", "experience_level": "intermediate", "equipment": "full gym", "training_frequency": "4x/week", "injuries_notes": None}
    context = assemble_context(None, None, None, [], profile=profile)
    assert "Jordan" in context
    assert "intermediate" in context
    assert "full gym" in context


def test_assemble_context_no_profile():
    context = assemble_context(None, None, None, [], profile=None)
    assert "NO USER PROFILE" in context


# -- task 1: _get_today_whoop returns today's data, not stale --

def test_get_today_whoop_returns_today(db):
    db.add(WhoopData(date="2020-01-01", recovery_score=50.0, hrv=40.0, resting_hr=60, sleep_score=70.0, sleep_duration=6.0, strain=8.0))
    db.add(WhoopData(date=date.today().isoformat(), recovery_score=85.0, hrv=72.0, resting_hr=50, sleep_score=90.0, sleep_duration=7.8, strain=12.5))
    db.commit()
    result = _get_today_whoop(db)
    assert result is not None
    assert result["recovery_score"] == 85.0
    assert result["hrv"] == 72.0
    assert result["resting_hr"] == 50
    assert result["sleep_score"] == 90.0
    assert result["sleep_duration"] == 7.8
    assert result["strain"] == 12.5


def test_get_today_whoop_returns_none_when_no_today(db):
    db.add(WhoopData(date="2020-01-01", recovery_score=50.0, hrv=40.0, resting_hr=60))
    db.commit()
    result = _get_today_whoop(db)
    assert result is None


# -- task 2: set history in context --

def test_assemble_context_with_set_history():
    set_history = [
        {"date": "2026-03-15", "exercise": "Bench Press", "weight": 225.0, "reps": 5, "rpe": 7.5},
        {"date": "2026-03-15", "exercise": "Bench Press", "weight": 225.0, "reps": 5, "rpe": 8.0},
    ]
    context = assemble_context(None, None, None, [], set_history=set_history)
    assert "Recent sets" in context
    assert "225.0lbs x 5 @ RPE 7.5" in context
    assert "Bench Press" in context


def test_assemble_context_without_set_history():
    context = assemble_context(None, None, None, [])
    assert "Recent sets" not in context


def test_get_recent_sets(db):
    w = Workout(date="2026-03-15", type="strength", status="completed")
    db.add(w)
    db.commit()
    ex = Exercise(workout_id=w.id, name="Bench Press", order=1)
    db.add(ex)
    db.commit()
    db.add(Set(exercise_id=ex.id, weight=225.0, reps=5, rpe=7.5, completed=True))
    db.add(Set(exercise_id=ex.id, weight=135.0, reps=10, rpe=5.0, completed=False))
    db.commit()
    result = _get_recent_sets(db)
    assert len(result) == 1
    assert result[0]["exercise"] == "Bench Press"
    assert result[0]["weight"] == 225.0


# -- task 3: recovery zones in context --

def test_recovery_zone_green():
    whoop = {"recovery_score": 85.0, "hrv": 65.0, "resting_hr": 50, "sleep_score": 90.0, "sleep_duration": 7.5, "strain": 12.0}
    context = assemble_context(None, None, whoop, [])
    assert "[GREEN]" in context
    assert "RHR 50" in context


def test_recovery_zone_yellow():
    whoop = {"recovery_score": 50.0, "hrv": 45.0, "resting_hr": 55, "sleep_score": 70.0, "sleep_duration": 6.5, "strain": None}
    context = assemble_context(None, None, whoop, [])
    assert "[YELLOW]" in context


def test_recovery_zone_red():
    whoop = {"recovery_score": 20.0, "hrv": 30.0, "resting_hr": 65, "sleep_score": 40.0, "sleep_duration": 4.5, "strain": 5.0}
    context = assemble_context(None, None, whoop, [])
    assert "[RED]" in context


def test_recovery_zone_none_score():
    whoop = {"recovery_score": None, "hrv": 30.0, "resting_hr": 65, "sleep_score": None, "sleep_duration": None, "strain": None}
    context = assemble_context(None, None, whoop, [])
    assert "[RED]" in context
    assert "Recovery N/A%" in context


@pytest.mark.asyncio
async def test_chat_returns_text_and_layout():
    with patch("server.services.claude_service._call_claude_stateless", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = '{"response": "Go heavy today", "layout": {"screen": "workout_session", "layout": [{"type": "header", "title": "Bench Day"}]}}'
        service = ClaudeService()
        result = await service.chat("what's my workout?", context="test context")
        assert "Go heavy" in result["response"]
        assert result["layout"]["screen"] == "workout_session"


@pytest.mark.asyncio
async def test_chat_extracts_profile():
    with patch("server.services.claude_service._call_claude_stateless", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = '{"response": "Nice to meet you!", "layout": null, "profile": {"name": "Jordan", "goals": "strength"}}'
        service = ClaudeService()
        result = await service.chat("I'm Jordan", context="test")
        assert result["profile"]["name"] == "Jordan"
        assert result["profile"]["goals"] == "strength"


# -- task 7: structured set suggestions from claude --

@pytest.mark.asyncio
async def test_chat_returns_set_suggestion():
    with patch("server.services.claude_service._call_claude_stateless", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = '{"response": "Hit 225 for 5 reps", "layout": null, "set_suggestion": {"exercise": "Bench Press", "weight": 225, "reps": 5, "basis": "based on last session"}}'
        service = ClaudeService()
        result = await service.chat("what should I do next?", context="test")
        assert result["set_suggestion"]["exercise"] == "Bench Press"
        assert result["set_suggestion"]["weight"] == 225
        assert result["set_suggestion"]["reps"] == 5
        assert result["set_suggestion"]["basis"] == "based on last session"


@pytest.mark.asyncio
async def test_chat_set_suggestion_null_when_absent():
    with patch("server.services.claude_service._call_claude_stateless", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = '{"response": "Just chatting", "layout": null}'
        service = ClaudeService()
        result = await service.chat("how are you?", context="test")
        assert result["set_suggestion"] is None


@pytest.mark.asyncio
async def test_chat_set_suggestion_null_on_parse_failure():
    with patch("server.services.claude_service._call_claude_stateless", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = "plain text, not json"
        service = ClaudeService()
        result = await service.chat("hello", context="test")
        assert result["set_suggestion"] is None
