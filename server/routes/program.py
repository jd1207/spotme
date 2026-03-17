import re
import logging
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from server.database import get_db
from server.models import SystemMemory, Workout, Exercise, Set, WhoopData

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/program")
async def get_program(db: Session = Depends(get_db)):
    memory = db.query(SystemMemory).filter_by(key="training_plan").first()
    if not memory or not memory.content:
        return {"has_program": False, "sections": [], "weeks": [], "progression": []}

    content = memory.content
    sections = _parse_sections(content)
    weeks = _parse_weeks(content)
    progression = _extract_progression(weeks)
    logged = _build_workout_map(db)
    whoop = _build_whoop_map(db)

    total = db.query(Workout).count()
    completed = db.query(Workout).filter_by(status="completed").count()

    return {
        "has_program": True,
        "sections": sections,
        "weeks": weeks,
        "progression": progression,
        "logged": logged,
        "whoop": whoop,
        "stats": {
            "total_workouts": total,
            "completed_workouts": completed,
            "today": date.today().isoformat(),
        },
    }


def _parse_sections(content: str) -> list[dict]:
    """parse ## sections into {title, content} pairs, excluding weeks section"""
    sections = []
    parts = re.split(r'^## ', content, flags=re.MULTILINE)
    for part in parts[1:]:
        lines = part.split('\n', 1)
        title = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ''
        if 'week' in title.lower() and 'program' in title.lower():
            continue
        sections.append({"title": title, "content": body})
    return sections


def _parse_weeks(content: str) -> list[dict]:
    """parse ### Week N entries into structured week objects"""
    weeks = []
    week_pattern = re.compile(r'^### (Week \d+.*?)$', re.MULTILINE)
    matches = list(week_pattern.finditer(content))

    for i, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[start:end].strip()

        items = []
        for line in body.split('\n'):
            line = line.strip()
            if line.startswith('- '):
                items.append(line[2:].strip())

        week_num_match = re.search(r'Week (\d+)', title)
        week_num = int(week_num_match.group(1)) if week_num_match else len(weeks) + 1

        weeks.append({"number": week_num, "title": title, "items": items})

    return weeks


def _extract_progression(weeks: list[dict]) -> list[dict]:
    """extract heaviest weight mentioned per week for bench progression"""
    progression = []
    for w in weeks:
        max_weight = 0
        for item in w.get("items", []):
            weights = re.findall(r'(\d{3})x\d+', item)
            for wt in weights:
                val = int(wt)
                if val > max_weight:
                    max_weight = val
        if max_weight > 0:
            progression.append({"week": w["number"], "weight": max_weight, "label": f"W{w['number']}"})
    return progression


def _build_workout_map(db: Session) -> dict:
    """match logged workouts to dates with exercise/set details"""
    workouts = db.query(Workout).order_by(Workout.date).all()
    workout_map = {}
    for w in workouts:
        exercises = db.query(Exercise).filter_by(workout_id=w.id).order_by(Exercise.order).all()
        ex_list = []
        for ex in exercises:
            sets = db.query(Set).filter_by(exercise_id=ex.id, completed=True).all()
            if sets:
                ex_list.append({
                    "name": ex.name,
                    "sets": [{"weight": s.weight, "reps": s.reps, "rpe": s.rpe} for s in sets],
                })
        workout_map[w.date] = {
            "status": w.status,
            "duration": w.duration,
            "exercises": ex_list,
        }
    return workout_map


def _build_whoop_map(db: Session) -> dict:
    """build date-keyed whoop recovery/hrv map"""
    whoop_rows = db.query(WhoopData).all()
    return {w.date: {"recovery": w.recovery_score, "hrv": w.hrv} for w in whoop_rows}
