import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from server.database import Base
from server.models import Program, Workout, Exercise, Set, WhoopData, Conversation

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

def test_create_program(db):
    program = Program(name="Bench Focus", goal="315 bench", phase="hypertrophy")
    db.add(program)
    db.commit()
    assert program.id is not None
    assert program.name == "Bench Focus"

def test_workout_with_exercises_and_sets(db):
    program = Program(name="Test", goal="test", phase="test")
    db.add(program)
    db.commit()
    workout = Workout(program_id=program.id, date="2026-03-16", type="strength", status="active")
    db.add(workout)
    db.commit()
    exercise = Exercise(workout_id=workout.id, name="Bench Press", order=1)
    db.add(exercise)
    db.commit()
    s = Set(exercise_id=exercise.id, weight=225, reps=5, rpe=7.5, completed=True)
    db.add(s)
    db.commit()
    assert s.id is not None
    assert s.weight == 225

def test_whoop_data(db):
    wd = WhoopData(date="2026-03-16", recovery_score=82.0, hrv=65.3, resting_hr=52, sleep_score=85.0, sleep_duration=7.5, strain=12.4)
    db.add(wd)
    db.commit()
    assert wd.recovery_score == 82.0

def test_conversation(db):
    msg = Conversation(role="user", content="how should I warm up?", context_type="chat")
    db.add(msg)
    db.commit()
    assert msg.id is not None
