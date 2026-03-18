from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from server.database import get_db
from server.schemas import ChatRequest, ChatResponse
from server.services.claude_service import ClaudeService, assemble_context
from sqlalchemy import func as sqlfunc
from server.models import (
    Program, Workout, Exercise, Set, WhoopData,
    Conversation, UserProfile, SystemMemory, Meal,
)
from server.config import settings

router = APIRouter()

MEMORY_KEY = "training_plan"


def _get_today_whoop(db: Session) -> dict | None:
    """return today's whoop data as a dict, or None"""
    whoop = db.query(WhoopData).filter_by(date=date.today().isoformat()).first()
    if not whoop:
        return None
    return {
        "recovery_score": whoop.recovery_score,
        "hrv": whoop.hrv,
        "resting_hr": whoop.resting_hr,
        "sleep_score": whoop.sleep_score,
        "sleep_duration": whoop.sleep_duration,
        "strain": whoop.strain,
    }


def _get_recent_sets(db: Session) -> list[dict]:
    """return last 15 completed sets across recent workouts"""
    rows = (
        db.query(Set, Exercise, Workout)
        .join(Exercise, Set.exercise_id == Exercise.id)
        .join(Workout, Exercise.workout_id == Workout.id)
        .filter(Set.completed == True)
        .order_by(Workout.date.desc(), Exercise.order, Set.id)
        .limit(15)
        .all()
    )
    return [
        {"date": w.date, "exercise": ex.name, "weight": s.weight, "reps": s.reps, "rpe": s.rpe}
        for s, ex, w in rows
    ]


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    # profile
    profile = db.query(UserProfile).first()
    profile_dict = None
    if profile:
        profile_dict = {
            "name": profile.name,
            "goals": profile.goals,
            "experience_level": profile.experience_level,
            "equipment": profile.equipment,
            "training_frequency": profile.training_frequency,
            "injuries_notes": profile.injuries_notes,
            "calorie_target": profile.calorie_target,
            "protein_target": profile.protein_target,
        }

    # whoop — today only
    whoop_dict = _get_today_whoop(db)

    # recent set history for context
    set_history = _get_recent_sets(db)

    # conversation history scoped to this workout (or general if no workout_id)
    history_query = db.query(Conversation).order_by(Conversation.created_at.desc())
    if request.workout_id:
        history_query = history_query.filter_by(workout_id=request.workout_id)
    else:
        history_query = history_query.filter_by(workout_id=None)
    history = history_query.limit(10).all()
    history_dicts = [{"role": h.role, "content": h.content} for h in reversed(history)]

    # current workout context if scoped
    workout_context = None
    if request.workout_id:
        workout = db.query(Workout).filter_by(id=request.workout_id).first()
        if workout:
            exercises = db.query(Exercise).filter_by(workout_id=workout.id).order_by(Exercise.order).all()
            ex_parts = []
            for ex in exercises:
                sets = db.query(Set).filter_by(exercise_id=ex.id).all()
                done = sum(1 for s in sets if s.completed)
                total = len(sets)
                ex_parts.append(f"{ex.name} ({done}/{total} sets done)")
            workout_context = f"Active workout ({workout.type}, {workout.date}): " + ", ".join(ex_parts) if ex_parts else None

    # system memory
    memory_row = db.query(SystemMemory).filter_by(key=MEMORY_KEY).first()
    memory_text = memory_row.content if memory_row else None

    # today's meal totals for context
    meal_row = db.query(
        sqlfunc.sum(Meal.calories).label("calories"),
        sqlfunc.sum(Meal.protein).label("protein"),
        sqlfunc.sum(Meal.carbs).label("carbs"),
        sqlfunc.sum(Meal.fat).label("fat"),
    ).filter(Meal.date == date.today().isoformat()).first()
    meal_totals = None
    if meal_row and meal_row.calories:
        meal_totals = {
            "calories": meal_row.calories,
            "protein": round(meal_row.protein or 0, 1),
            "carbs": round(meal_row.carbs or 0, 1),
            "fat": round(meal_row.fat or 0, 1),
        }

    context = assemble_context(None, None, whoop_dict, history_dicts, profile_dict, memory_text, workout_context, set_history=set_history, meal_totals=meal_totals)
    service = ClaudeService()
    result = await service.chat(request.message, context)

    # auto-save profile
    profile_data = result.get("profile")
    if profile_data and isinstance(profile_data, dict):
        if profile:
            for key in ["name", "goals", "experience_level", "equipment", "training_frequency", "injuries_notes", "calorie_target", "protein_target"]:
                if key in profile_data and profile_data[key] is not None:
                    setattr(profile, key, profile_data[key])
        else:
            profile = UserProfile(
                name=profile_data.get("name", ""),
                goals=profile_data.get("goals"),
                experience_level=profile_data.get("experience_level"),
                equipment=profile_data.get("equipment"),
                training_frequency=profile_data.get("training_frequency"),
                injuries_notes=profile_data.get("injuries_notes"),
                calorie_target=profile_data.get("calorie_target"),
                protein_target=profile_data.get("protein_target"),
            )
            db.add(profile)

    # auto-save memory
    memory_update = result.get("memory_update")
    if memory_update and isinstance(memory_update, str):
        if memory_row:
            memory_row.content = memory_update
        else:
            db.add(SystemMemory(key=MEMORY_KEY, content=memory_update))

    # auto-save meal if claude estimated macros
    meal_data = result.get("meal")
    if meal_data and isinstance(meal_data, dict):
        db.add(Meal(
            date=date.today().isoformat(),
            description=meal_data.get("description", ""),
            calories=meal_data.get("calories"),
            protein=meal_data.get("protein"),
            carbs=meal_data.get("carbs"),
            fat=meal_data.get("fat"),
            meal_type=meal_data.get("meal_type"),
        ))

    # save messages
    db.add(Conversation(role="user", content=request.message, context_type="chat", workout_id=request.workout_id))
    db.add(Conversation(role="assistant", content=result["response"], context_type="chat", workout_id=request.workout_id))
    db.commit()
    return ChatResponse(response=result["response"], layout=result.get("layout"), set_suggestion=result.get("set_suggestion"))


@router.get("/chat/history/{workout_id}")
async def get_workout_chat(workout_id: int, db: Session = Depends(get_db)):
    messages = db.query(Conversation).filter_by(workout_id=workout_id).order_by(Conversation.created_at).all()
    return [{"role": m.role, "content": m.content, "created_at": str(m.created_at)} for m in messages]


@router.post("/intake")
async def intake(data: dict, db: Session = Depends(get_db)):
    # save profile
    profile = db.query(UserProfile).first()
    if not profile:
        profile = UserProfile(name=data.get("name", ""))
        db.add(profile)
    for key in ["name", "goals", "experience_level", "equipment", "training_frequency", "injuries_notes"]:
        if key in data and data[key]:
            setattr(profile, key, data[key])
    db.commit()

    # if training plan text provided, ask Claude to parse and store as memory
    plan_text = data.get("training_plan", "")
    if plan_text:
        service = ClaudeService()
        profile_summary = f"Athlete: {profile.name}, {profile.experience_level}, goals: {profile.goals}, equipment: {profile.equipment}, frequency: {profile.training_frequency}"
        if profile.injuries_notes:
            profile_summary += f", limitations: {profile.injuries_notes}"
        prompt = f"Here is my training plan and background. Store this as your training memory. Summarize what you understand and confirm you're ready to coach me.\n\n{plan_text}"
        context = assemble_context(None, None, None, [], {
            "name": profile.name, "goals": profile.goals,
            "experience_level": profile.experience_level,
            "equipment": profile.equipment,
            "training_frequency": profile.training_frequency,
            "injuries_notes": profile.injuries_notes,
        })
        result = await service.chat(prompt, context)

        # save memory — use Claude's structured update if available, fall back to raw plan
        memory_update = result.get("memory_update") or plan_text
        memory_row = db.query(SystemMemory).filter_by(key=MEMORY_KEY).first()
        if memory_row:
            memory_row.content = memory_update
        else:
            db.add(SystemMemory(key=MEMORY_KEY, content=memory_update))

        db.add(Conversation(role="user", content=prompt, context_type="intake"))
        db.add(Conversation(role="assistant", content=result["response"], context_type="intake"))
        db.commit()
        return {"status": "ok", "response": result["response"]}

    db.commit()
    return {"status": "ok", "response": None}
