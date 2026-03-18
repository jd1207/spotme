from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from server.database import get_db
from server.models import UserProfile

router = APIRouter()


@router.get("/profile")
async def get_profile(db: Session = Depends(get_db)):
    profile = db.query(UserProfile).first()
    if not profile:
        return None
    return {
        "id": profile.id,
        "name": profile.name,
        "goals": profile.goals,
        "experience_level": profile.experience_level,
        "equipment": profile.equipment,
        "training_frequency": profile.training_frequency,
        "injuries_notes": profile.injuries_notes,
        "calorie_target": profile.calorie_target,
        "protein_target": profile.protein_target,
    }


@router.post("/profile")
async def save_profile(data: dict, db: Session = Depends(get_db)):
    profile = db.query(UserProfile).first()
    if profile:
        for key in ["name", "goals", "experience_level", "equipment", "training_frequency", "injuries_notes", "calorie_target", "protein_target"]:
            if key in data and data[key] is not None:
                setattr(profile, key, data[key])
    else:
        profile = UserProfile(
            name=data.get("name", ""),
            goals=data.get("goals"),
            experience_level=data.get("experience_level"),
            equipment=data.get("equipment"),
            training_frequency=data.get("training_frequency"),
            injuries_notes=data.get("injuries_notes"),
            calorie_target=data.get("calorie_target"),
            protein_target=data.get("protein_target"),
        )
        db.add(profile)
    db.commit()
    db.refresh(profile)
    return {"id": profile.id, "name": profile.name}
