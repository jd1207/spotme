import pytest
from unittest.mock import AsyncMock, patch
from server.services.claude_service import ClaudeService, assemble_context

def test_assemble_context():
    whoop = {"recovery_score": 85.0, "hrv": 65.0, "sleep_score": 90.0}
    history = [{"role": "user", "content": "how should I warm up?"}, {"role": "assistant", "content": "start with the bar"}]
    profile = {"name": "Jordan", "goals": "strength", "experience_level": "advanced", "equipment": "full gym", "training_frequency": "4x/week", "injuries_notes": None}
    memory = "# Bench Focus Program\nGoal: 315 bench"
    context = assemble_context(None, None, whoop, history, profile=profile, memory=memory)
    assert "Jordan" in context
    assert "85.0" in context
    assert "Bench Focus" in context
    assert "how should I warm up?" in context

def test_assemble_context_missing_data():
    context = assemble_context(program=None, workout=None, whoop=None, history=[])
    assert "no user profile" in context.lower()

def test_assemble_context_with_profile():
    profile = {"name": "Jordan", "goals": "strength", "experience_level": "intermediate", "equipment": "full gym", "training_frequency": "4x/week", "injuries_notes": None}
    context = assemble_context(None, None, None, [], profile=profile)
    assert "Jordan" in context
    assert "intermediate" in context
    assert "full gym" in context

def test_assemble_context_no_profile():
    context = assemble_context(None, None, None, [], profile=None)
    assert "NO USER PROFILE" in context

@pytest.mark.asyncio
async def test_chat_returns_text_and_layout():
    with patch("server.services.claude_service._call_claude", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = '{"response": "Go heavy today", "layout": {"screen": "workout_session", "layout": [{"type": "header", "title": "Bench Day"}]}}'
        service = ClaudeService()
        result = await service.chat("what's my workout?", context="test context")
        assert "Go heavy" in result["response"]
        assert result["layout"]["screen"] == "workout_session"

@pytest.mark.asyncio
async def test_chat_extracts_profile():
    with patch("server.services.claude_service._call_claude", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = '{"response": "Nice to meet you!", "layout": null, "profile": {"name": "Jordan", "goals": "strength"}}'
        service = ClaudeService()
        result = await service.chat("I'm Jordan", context="test")
        assert result["profile"]["name"] == "Jordan"
        assert result["profile"]["goals"] == "strength"
