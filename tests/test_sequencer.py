import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from server.database import Base
from server.models import Workout, Exercise, Set
from server.config import today_eastern


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    session = sessionmaker(bind=eng)()
    yield session
    session.close()


SAMPLE_PLAN = [
    {"exercise": "Bench Press", "set_type": "warmup", "weight": 135, "reps": 10},
    {"exercise": "Bench Press", "set_type": "warmup", "weight": 185, "reps": 5},
    {"exercise": "Bench Press", "set_type": "working", "weight": 235, "reps": 6},
    {"exercise": "Bench Press", "set_type": "working", "weight": 235, "reps": 6},
    {"exercise": "DB Press", "set_type": "working", "weight": 80, "reps": 10},
]


def test_create_workout_from_plan(db):
    from server.services.workout_sequencer import create_workout_from_plan
    result = create_workout_from_plan(db, SAMPLE_PLAN, today_eastern())
    assert result["workout_id"] is not None
    assert result["first_set"] is not None
    assert result["first_set"]["exercise"] == "Bench Press"
    assert result["first_set"]["set_type"] == "warmup"
    assert result["first_set"]["weight"] == 135
    assert result["total_sets"] == 5


def test_create_workout_sets_order(db):
    from server.services.workout_sequencer import create_workout_from_plan
    result = create_workout_from_plan(db, SAMPLE_PLAN, today_eastern())
    workout_id = result["workout_id"]
    exercises = db.query(Exercise).filter_by(workout_id=workout_id).all()
    all_sets = []
    for ex in exercises:
        sets = db.query(Set).filter_by(exercise_id=ex.id).order_by(Set.order).all()
        all_sets.extend(sets)
    orders = [s.order for s in all_sets]
    assert orders == [0, 1, 2, 3, 4]
    assert all(s.status == "pending" for s in all_sets)
    assert all(not s.completed for s in all_sets)


def test_get_next_set(db):
    from server.services.workout_sequencer import create_workout_from_plan, get_next_set
    result = create_workout_from_plan(db, SAMPLE_PLAN, today_eastern())
    next_set = get_next_set(db, result["workout_id"])
    assert next_set is not None
    assert next_set["exercise"] == "Bench Press"
    assert next_set["order"] == 0


def test_complete_set(db):
    from server.services.workout_sequencer import create_workout_from_plan, complete_set
    result = create_workout_from_plan(db, SAMPLE_PLAN, today_eastern())
    first_id = result["first_set"]["id"]
    completed = complete_set(db, first_id, 135, 10, None, None)
    assert completed["logged_set"]["status"] == "completed"
    assert completed["next_set"] is not None
    assert completed["next_set"]["weight"] == 185  # second warmup
    assert completed["progress"]["completed"] == 1
    assert completed["progress"]["total"] == 5


def test_complete_set_with_feel(db):
    from server.services.workout_sequencer import create_workout_from_plan, complete_set
    result = create_workout_from_plan(db, SAMPLE_PLAN, today_eastern())
    # complete warmups
    first_id = result["first_set"]["id"]
    r = complete_set(db, first_id, 135, 10, None, None)
    r = complete_set(db, r["next_set"]["id"], 185, 5, None, None)
    # now working set with feel
    r = complete_set(db, r["next_set"]["id"], 235, 6, None, "tough")
    s = db.query(Set).filter_by(id=r["logged_set"]["id"]).first()
    assert s.rpe == 9.0  # tough maps to 9.0


def test_complete_all_sets(db):
    from server.services.workout_sequencer import create_workout_from_plan, complete_set
    plan = [
        {"exercise": "Bench", "set_type": "working", "weight": 225, "reps": 5},
        {"exercise": "Bench", "set_type": "working", "weight": 225, "reps": 5},
    ]
    result = create_workout_from_plan(db, plan, today_eastern())
    r = complete_set(db, result["first_set"]["id"], 225, 5, None, None)
    r = complete_set(db, r["next_set"]["id"], 225, 5, None, None)
    assert r["next_set"] is None
    assert r["progress"]["completed"] == 2


def test_replace_pending_sets(db):
    from server.services.workout_sequencer import create_workout_from_plan, complete_set, replace_pending_sets
    result = create_workout_from_plan(db, SAMPLE_PLAN, today_eastern())
    # complete first set
    first_id = result["first_set"]["id"]
    complete_set(db, first_id, 135, 10, None, None)
    # replace remaining with new plan
    new_plan = [
        {"exercise": "Bench Press", "set_type": "working", "weight": 225, "reps": 6},
        {"exercise": "Bench Press", "set_type": "working", "weight": 225, "reps": 6},
    ]
    replaced = replace_pending_sets(db, result["workout_id"], new_plan)
    assert replaced["next_set"]["weight"] == 225
    assert replaced["total_remaining"] == 2
    # original completed set still exists
    completed_sets = db.query(Set).join(Exercise).filter(
        Exercise.workout_id == result["workout_id"],
        Set.status == "completed"
    ).all()
    assert len(completed_sets) == 1


def test_skip_set(db):
    from server.services.workout_sequencer import create_workout_from_plan, complete_set
    result = create_workout_from_plan(db, SAMPLE_PLAN, today_eastern())
    first_id = result["first_set"]["id"]
    # skip by passing actual_weight=0, actual_reps=0 and the sequencer marks as skipped
    # actually, skip is handled by a separate mechanism - let's test via status
    s = db.query(Set).filter_by(id=first_id).first()
    s.status = "skipped"
    s.completed = False
    db.commit()
    from server.services.workout_sequencer import get_next_set
    next_set = get_next_set(db, result["workout_id"])
    assert next_set["order"] == 1  # skipped order 0, now on order 1
