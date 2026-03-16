import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from server.services.claude_service import ClaudeService, assemble_context

def test_assemble_context():
    program = {"name": "Bench Focus", "goal": "315 bench", "phase": "strength"}
    whoop = {"recovery_score": 85.0, "hrv": 65.0, "sleep_score": 90.0}
    history = [{"role": "user", "content": "how should I warm up?"}, {"role": "assistant", "content": "start with the bar"}]
    context = assemble_context(program, None, whoop, history)
    assert "Bench Focus" in context
    assert "85.0" in context
    assert "how should I warm up?" in context

def test_assemble_context_missing_data():
    context = assemble_context(program=None, workout=None, whoop=None, history=[])
    assert "unavailable" in context.lower() or "no active" in context.lower()

@pytest.mark.asyncio
async def test_chat_returns_text_and_layout():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"response": "Go heavy today", "layout": {"screen": "workout_session", "layout": [{"type": "header", "title": "Bench Day"}]}}')]
    with patch("server.services.claude_service.anthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_anthropic.AsyncAnthropic.return_value = mock_client
        service = ClaudeService(api_key="test-key")
        result = await service.chat("what's my workout?", context="test context")
        assert "Go heavy" in result["response"]
        assert result["layout"]["screen"] == "workout_session"
