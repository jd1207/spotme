from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from server.database import get_db
from server.models import Meal

router = APIRouter()


@router.post("/meals")
async def log_meal(data: dict, db: Session = Depends(get_db)):
    """quick-add a meal with macros"""
    meal = Meal(
        date=data.get("date", date.today().isoformat()),
        description=data.get("description", ""),
        calories=data.get("calories"),
        protein=data.get("protein"),
        carbs=data.get("carbs"),
        fat=data.get("fat"),
        meal_type=data.get("meal_type"),
    )
    db.add(meal)
    db.commit()
    return {"id": meal.id, "logged": True}


@router.get("/meals/today")
async def get_today_meals(db: Session = Depends(get_db)):
    """get all meals and totals for today"""
    today = date.today().isoformat()
    meals = db.query(Meal).filter_by(date=today).order_by(Meal.created_at).all()
    total_cal = sum(m.calories or 0 for m in meals)
    total_protein = sum(m.protein or 0 for m in meals)
    total_carbs = sum(m.carbs or 0 for m in meals)
    total_fat = sum(m.fat or 0 for m in meals)
    return {
        "date": today,
        "meals": [
            {
                "id": m.id,
                "description": m.description,
                "calories": m.calories,
                "protein": m.protein,
                "carbs": m.carbs,
                "fat": m.fat,
                "meal_type": m.meal_type,
            }
            for m in meals
        ],
        "totals": {
            "calories": total_cal,
            "protein": round(total_protein, 1),
            "carbs": round(total_carbs, 1),
            "fat": round(total_fat, 1),
        },
    }


@router.get("/meals/week")
async def get_week_meals(db: Session = Depends(get_db)):
    """get daily totals for the past 7 days"""
    today = date.today()
    week_ago = (today - timedelta(days=6)).isoformat()
    rows = (
        db.query(
            Meal.date,
            func.sum(Meal.calories).label("calories"),
            func.sum(Meal.protein).label("protein"),
        )
        .filter(Meal.date >= week_ago)
        .group_by(Meal.date)
        .order_by(Meal.date)
        .all()
    )
    return {
        "days": [
            {
                "date": r.date,
                "calories": r.calories or 0,
                "protein": round(r.protein or 0, 1),
            }
            for r in rows
        ]
    }


@router.delete("/meals/{meal_id}")
async def delete_meal(meal_id: int, db: Session = Depends(get_db)):
    meal = db.query(Meal).filter_by(id=meal_id).first()
    if meal:
        db.delete(meal)
        db.commit()
        return {"deleted": True}
    return {"deleted": False, "error": "not found"}
