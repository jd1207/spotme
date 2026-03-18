import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from server.database import Base, get_db
from server.models import Meal
from server.config import today_eastern


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    session = sessionmaker(bind=eng)()
    yield session
    session.close()

@pytest.fixture
def client(db):
    from server.main import create_app
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def test_meals_day_endpoint(db, client):
    today = today_eastern()
    db.add(Meal(date=today, description="eggs and toast", calories=350, protein=20, carbs=30, fat=15))
    db.commit()
    resp = client.get(f"/api/meals/day/{today}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["meals"]) == 1
    assert data["totals"]["calories"] == 350


def test_meals_day_with_items(db, client):
    import json
    today = today_eastern()
    db.add(Meal(date=today, description="chicken and rice", calories=650, protein=55,
                items=json.dumps(["200g chicken breast", "Cup of rice"])))
    db.commit()
    resp = client.get(f"/api/meals/day/{today}")
    meal = resp.json()["meals"][0]
    assert meal["items"] == ["200g chicken breast", "Cup of rice"]


def test_meals_day_empty(client):
    resp = client.get("/api/meals/day/2020-01-01")
    assert resp.json()["meals"] == []
    assert resp.json()["totals"]["calories"] == 0


def test_log_meal_with_items(client):
    resp = client.post("/api/meals", json={
        "description": "steak dinner",
        "calories": 800,
        "protein": 70,
        "items": ["12oz ribeye", "Baked potato", "Caesar salad"],
    })
    assert resp.json()["logged"] is True

    today = client.get(f"/api/meals/day/{today_eastern()}").json()
    assert today["meals"][0]["items"] == ["12oz ribeye", "Baked potato", "Caesar salad"]
