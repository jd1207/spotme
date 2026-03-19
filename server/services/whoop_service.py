from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from server.models import WhoopData, WhoopSyncQueue, Workout, Exercise, Set

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
STALENESS_THRESHOLD = 7200  # 2 hours in seconds

_sync_lock = asyncio.Lock()


def get_whoop_client(db):
    """create a whoop client with auto-refresh from stored tokens."""
    from whoop import WhoopClient, TokenSet
    from server.models import WhoopToken

    stored = db.query(WhoopToken).first()
    if not stored:
        raise HTTPException(400, "whoop not connected — login first")

    token_set = TokenSet(
        access_token=stored.access_token,
        refresh_token=stored.refresh_token,
        expires_at=stored.expires_at.timestamp() if stored.expires_at else 0,
    )

    def persist_refreshed_tokens(new_tokens):
        stored.access_token = new_tokens.access_token
        stored.refresh_token = new_tokens.refresh_token
        stored.expires_at = datetime.fromtimestamp(new_tokens.expires_at)
        db.commit()

    return WhoopClient(
        token_set=token_set,
        on_token_refresh=persist_refreshed_tokens,
    )



async def sync_whoop_biometrics(db: Session, force=False):
    """sync biometrics from whoop, skipping if data is fresh."""
    async with _sync_lock:
        if not force:
            from server.config import today_eastern
            latest = db.query(WhoopData).filter(
                WhoopData.date == today_eastern()
            ).first()
            if latest and latest.synced_at:
                age = (datetime.utcnow() - latest.synced_at).total_seconds()
                if age < STALENESS_THRESHOLD:
                    return {"skipped": True, "reason": "fresh"}

        try:
            client = get_whoop_client(db)
        except Exception as e:
            return {"error": str(e), "synced": 0}

        from whoop import WhoopAPIError
        try:
            recoveries = await client.get_recovery()
            sleeps = await client.get_sleep()
        except WhoopAPIError as e:
            logger.warning("whoop biometric sync failed: %s", e)
            return {"error": str(e), "synced": 0}

        synced = 0
        warnings = []
        for r in recoveries:
            date_str = r.created_at[:10]
            existing = db.query(WhoopData).filter_by(date=date_str).first()
            if not existing:
                db.add(WhoopData(
                    date=date_str,
                    recovery_score=r.recovery_score,
                    hrv=r.hrv,
                    resting_hr=int(r.resting_hr),
                ))
                synced += 1
        for s in sleeps:
            date_str = s.created_at[:10]
            existing = db.query(WhoopData).filter_by(date=date_str).first()
            if existing:
                existing.sleep_score = s.performance
                existing.sleep_duration = s.total_in_bed_hours

        # strain from cycles — fetched independently since scope may not be granted
        try:
            cycles = await client.get_cycles()
            for c in cycles:
                date_str = c.start[:10]
                existing = db.query(WhoopData).filter_by(date=date_str).first()
                if existing:
                    existing.strain = c.strain
        except WhoopAPIError as e:
            logger.warning("whoop cycle/strain sync skipped: %s", e)
            warnings.append(f"strain unavailable: {e}")

        db.commit()
        result = {"synced": synced}
        if warnings:
            result["warnings"] = warnings
        return result


async def push_workout_to_whoop(db: Session, workout_id: int):
    """sync a completed workout to whoop with detailed exercises."""
    try:
        from whoop import DetailedExercise, ExerciseSet
    except ImportError:
        return {"synced": False, "error": "whoop-write-api not installed"}

    workout = db.query(Workout).filter_by(id=workout_id).first()
    if not workout:
        return {"synced": False, "error": "workout not found"}

    exercises = db.query(Exercise).filter_by(workout_id=workout_id).all()
    whoop_exercises = []
    for ex in exercises:
        completed_sets = db.query(Set).filter_by(
            exercise_id=ex.id, completed=True
        ).all()
        if not completed_sets:
            continue
        whoop_exercises.append(DetailedExercise(
            exercise_id=ex.whoop_exercise_id or ex.name.upper().replace(" ", "_"),
            name=ex.name,
            sets=[ExerciseSet(reps=s.reps, weight=s.weight) for s in completed_sets],
        ))

    try:
        from server.config import TIMEZONE
        from datetime import timedelta
        end = datetime.now(TIMEZONE)
        duration = workout.duration or 60
        start = end - timedelta(minutes=duration)

        client = get_whoop_client(db)
        activity = await client.create_activity(
            "weightlifting",
            start=start.isoformat(),
            end=end.isoformat(),
        )

        if whoop_exercises:
            await client.link_exercises_detailed(activity.id, whoop_exercises)

        workout.whoop_activity_id = activity.id
        db.commit()
        return {"synced": True, "activity_id": activity.id}
    except Exception as e:
        _queue_failed_sync(db, workout_id, workout.date, e)
        return {"synced": False, "error": str(e), "queued": True}


async def process_whoop_queue(db: Session):
    from whoop import WorkoutWrite, ExerciseWrite, WhoopAPIError
    from server.models import WhoopToken

    if not db.query(WhoopToken).first():
        return {"processed": 0, "error": "whoop not configured"}

    pending = (
        db.query(WhoopSyncQueue)
        .filter(WhoopSyncQueue.status == "pending")
        .filter(WhoopSyncQueue.retries < MAX_RETRIES)
        .all()
    )
    if not pending:
        return {"processed": 0}

    try:
        client = get_whoop_client(db)
    except (ImportError, HTTPException, ValueError) as e:
        return {"processed": 0, "error": str(e)}

    processed = 0
    for item in pending:
        workout = db.query(Workout).filter_by(id=item.workout_id).first()
        if not workout:
            item.status = "failed"
            item.last_error = "workout deleted"
            continue

        exercises = db.query(Exercise).filter_by(workout_id=workout.id).all()
        exercise_writes = []
        for ex in exercises:
            sets = db.query(Set).filter_by(exercise_id=ex.id, completed=True).all()
            if sets:
                exercise_writes.append(ExerciseWrite(
                    name=ex.name,
                    sets=len(sets),
                    reps=sets[0].reps,
                    weight=sets[0].weight,
                ))

        duration_mins = workout.duration or 60
        start_ts = f"{workout.date}T12:00:00.000Z"
        end_hour = 12 + (duration_mins // 60)
        end_min = duration_mins % 60
        end_ts = f"{workout.date}T{end_hour:02d}:{end_min:02d}:00.000Z"

        whoop_workout = WorkoutWrite(
            sport_id=1,
            start=start_ts,
            end=end_ts,
            exercises=exercise_writes,
        )

        try:
            await client.log_workout(whoop_workout)
            item.status = "synced"
            processed += 1
        except WhoopAPIError as e:
            item.retries += 1
            item.last_error = str(e)
            if item.retries >= MAX_RETRIES:
                item.status = "failed"
            logger.warning(
                "whoop queue retry %d/%d for workout %d: %s",
                item.retries, MAX_RETRIES, item.workout_id, e,
            )

    db.commit()
    return {"processed": processed, "remaining": len(pending) - processed}


async def populate_exercise_catalog(db):
    """fetch full exercise catalog from whoop and cache locally."""
    from server.models import ExerciseCatalog

    client = get_whoop_client(db)
    catalog = await client.get_exercises()

    # clear existing and repopulate
    db.query(ExerciseCatalog).delete()
    for ex in catalog.exercises:
        db.add(ExerciseCatalog(
            whoop_id=ex.id, name=ex.name,
            equipment=getattr(ex, 'equipment', None),
            muscle_group=getattr(ex, 'muscle_group', None),
        ))
    db.commit()


def compute_journal_state(db, date_str):
    """compute accumulated journal signals from all meals on a date."""
    from server.models import Meal
    meals = db.query(Meal).filter(Meal.date == date_str).all()
    caffeine = 0
    alcohol = False
    late_meal = False
    protein = 0

    for meal in meals:
        if meal.journal_signals:
            signals = json.loads(meal.journal_signals) if isinstance(meal.journal_signals, str) else meal.journal_signals
            caffeine += signals.get("caffeine", 0)
            if signals.get("alcohol", False):
                alcohol = True
        if meal.created_at and meal.created_at.hour >= 20:
            late_meal = True
        protein += meal.protein or 0

    return {"caffeine": caffeine, "alcohol": alcohol, "late_meal": late_meal, "protein": int(protein)}


async def sync_journal_to_whoop(db, date_str):
    """sync accumulated journal signals to whoop."""
    try:
        from whoop import JournalInput
    except ImportError:
        return {"synced": False, "error": "whoop-write-api not installed"}

    state = compute_journal_state(db, date_str)
    journal_inputs = []

    if state["caffeine"] > 0:
        journal_inputs.append(JournalInput(
            behavior_tracker_id=2, answered_yes=True,
            magnitude_input_value=state["caffeine"],
        ))
    journal_inputs.append(JournalInput(
        behavior_tracker_id=1, answered_yes=state["alcohol"],
    ))
    if state["late_meal"]:
        journal_inputs.append(JournalInput(
            behavior_tracker_id=6, answered_yes=True,
        ))
    if state["protein"] > 0:
        journal_inputs.append(JournalInput(
            behavior_tracker_id=89, answered_yes=True,
            magnitude_input_value=state["protein"],
        ))

    try:
        client = get_whoop_client(db)
        await client.log_journal(date_str, journal_inputs)
        return {"synced": True}
    except Exception as e:
        _queue_failed_sync(db, None, date_str, e, sync_type="journal")
        return {"synced": False, "error": str(e), "queued": True}


def _queue_failed_sync(db: Session, workout_id: int, date: str, error: Exception, sync_type: str = "workout"):
    db.add(WhoopSyncQueue(
        workout_id=workout_id,
        payload=json.dumps({"date": date}),
        status="pending",
        last_error=str(error),
        sync_type=sync_type,
    ))
    db.commit()
    logger.info("queued failed whoop sync for workout %s", workout_id)
