import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_call_claude_returns_json_response():
    """_call_claude uses Anthropic SDK and returns parsed JSON."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"response": "test reply", "layout": null}')]
    mock_response.stop_reason = "end_turn"

    with patch("server.services.claude_service.anthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        from server.services.claude_service import _call_claude
        result = await _call_claude("test system prompt", "hello")

        assert '"response"' in result
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-sonnet-4-20250514"
        assert call_kwargs["system"] == "test system prompt"


@pytest.mark.asyncio
async def test_call_claude_passes_message_as_user_role():
    """_call_claude sends the message with user role."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"response": "ok", "layout": null}')]

    with patch("server.services.claude_service.anthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        from server.services.claude_service import _call_claude
        await _call_claude("sys", "user message here")

        call_kwargs = mock_client.messages.create.call_args[1]
        messages = call_kwargs["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "user message here"


@pytest.mark.asyncio
async def test_call_claude_extracts_json_from_fenced_response():
    """_call_claude applies _extract_json to strip markdown fences."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='```json\n{"response": "fenced", "layout": null}\n```')]

    with patch("server.services.claude_service.anthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        from server.services.claude_service import _call_claude
        result = await _call_claude("sys", "msg")

        assert '"response"' in result
        assert "```" not in result
