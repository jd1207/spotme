import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from server.database import Base, get_db
from server.models import Meal
from server.main import create_app


@pytest.fixture
def db():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    session = sessionmaker(bind=eng)()
    yield session
    session.close()


@pytest.fixture
def client(db):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def test_log_meal_and_retrieve(client):
    resp = client.post("/api/meals", json={
        "description": "chicken and rice",
        "calories": 650,
        "protein": 55,
        "carbs": 60,
        "fat": 12,
        "meal_type": "lunch",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["logged"] is True
    assert data["id"] is not None

    today = client.get("/api/meals/today").json()
    assert len(today["meals"]) == 1
    assert today["meals"][0]["description"] == "chicken and rice"
    assert today["meals"][0]["calories"] == 650


def test_today_totals(client):
    client.post("/api/meals", json={
        "description": "eggs",
        "calories": 210,
        "protein": 18,
        "carbs": 0,
        "fat": 15,
    })
    client.post("/api/meals", json={
        "description": "protein shake",
        "calories": 300,
        "protein": 50,
        "carbs": 10,
        "fat": 5,
    })
    today = client.get("/api/meals/today").json()
    assert today["totals"]["calories"] == 510
    assert today["totals"]["protein"] == 68.0
    assert today["totals"]["carbs"] == 10.0
    assert today["totals"]["fat"] == 20.0


def test_week_aggregation(db, client):
    today = date.today()
    yesterday = (today - timedelta(days=1)).isoformat()
    db.add(Meal(date=yesterday, description="steak", calories=800, protein=70))
    db.add(Meal(date=today.isoformat(), description="salad", calories=300, protein=20))
    db.commit()
    resp = client.get("/api/meals/week").json()
    assert len(resp["days"]) == 2
    dates = [d["date"] for d in resp["days"]]
    assert yesterday in dates
    assert today.isoformat() in dates


def test_delete_meal(client):
    resp = client.post("/api/meals", json={
        "description": "donut",
        "calories": 300,
    })
    meal_id = resp.json()["id"]
    del_resp = client.delete(f"/api/meals/{meal_id}")
    assert del_resp.json()["deleted"] is True

    today = client.get("/api/meals/today").json()
    assert len(today["meals"]) == 0


def test_delete_nonexistent_meal(client):
    resp = client.delete("/api/meals/9999")
    assert resp.json()["deleted"] is False
    assert resp.json()["error"] == "not found"


def test_meal_defaults_to_today(db, client):
    client.post("/api/meals", json={"description": "snack", "calories": 100})
    meals = db.query(Meal).all()
    assert len(meals) == 1
    assert meals[0].date == date.today().isoformat()


def test_today_totals_empty(client):
    today = client.get("/api/meals/today").json()
    assert today["totals"]["calories"] == 0
    assert today["totals"]["protein"] == 0
    assert len(today["meals"]) == 0
