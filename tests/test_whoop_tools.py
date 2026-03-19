import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_create_activity_tool():
    with patch("server.services.whoop_service.get_whoop_client") as mock_factory:
        mock_client = AsyncMock()
        mock_factory.return_value = mock_client
        mock_client.create_activity = AsyncMock(return_value=MagicMock(id="uuid-123"))

        from server.services.whoop_tools import execute_whoop_tool
        result = await execute_whoop_tool(
            "create_whoop_activity",
            {"activity_type": "sauna", "duration_minutes": 20},
            MagicMock(),
        )

    assert result["success"] is True
    assert result["activity_id"] == "uuid-123"


@pytest.mark.asyncio
async def test_unknown_tool_returns_error():
    from server.services.whoop_tools import execute_whoop_tool
    result = await execute_whoop_tool("nonexistent_tool", {}, MagicMock())
    assert "error" in result
    assert "unknown" in result["error"]


@pytest.mark.asyncio
async def test_search_catalog_tool():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from server.database import Base
    from server.models import ExerciseCatalog

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    db.add(ExerciseCatalog(whoop_id="BENCHPRESS_BARBELL", name="Bench Press", equipment="BARBELL"))
    db.add(ExerciseCatalog(whoop_id="SQUAT_BARBELL", name="Squat", equipment="BARBELL"))
    db.commit()

    from server.services.whoop_tools import execute_whoop_tool
    result = await execute_whoop_tool("search_exercise_catalog", {"query": "bench"}, db)
    assert result["success"] is True
    assert len(result["exercises"]) == 1
    assert result["exercises"][0]["name"] == "Bench Press"

    db.close()


@pytest.mark.asyncio
async def test_tool_error_handling():
    with patch("server.services.whoop_service.get_whoop_client") as mock_factory:
        mock_factory.side_effect = Exception("whoop disconnected")

        from server.services.whoop_tools import execute_whoop_tool
        result = await execute_whoop_tool(
            "create_whoop_activity",
            {"activity_type": "sauna", "duration_minutes": 20},
            MagicMock(),
        )

    assert "error" in result
    assert "disconnected" in result["error"]
