import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from unittest import mock


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


@pytest.mark.asyncio
async def test_tool_use_loop_executes_tool():
    """When Claude returns tool_use, server executes and sends result back."""
    # first call: Claude wants to use a tool
    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.id = "call_123"
    tool_use_block.name = "create_whoop_activity"
    tool_use_block.input = {"activity_type": "sauna", "duration_minutes": 20}

    tool_use_response = MagicMock()
    tool_use_response.content = [tool_use_block]
    tool_use_response.stop_reason = "tool_use"

    # second call: Claude gives final text response
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = '{"response": "Logged 20-min sauna to Whoop.", "layout": null}'

    final_response = MagicMock()
    final_response.content = [text_block]
    final_response.stop_reason = "end_turn"

    with patch("server.services.claude_service.anthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(
            side_effect=[tool_use_response, final_response]
        )

        mock_tool_executor = AsyncMock(return_value={"success": True, "activity_id": "uuid-123"})

        from server.services.claude_service import _call_claude_with_tools
        result = await _call_claude_with_tools(
            system_prompt="test",
            message="log a sauna",
            tools=[{"name": "create_whoop_activity", "description": "test", "input_schema": {}}],
            tool_executor=mock_tool_executor,
            db=MagicMock(),
        )

    assert "Logged 20-min sauna" in result
    mock_tool_executor.assert_called_once_with(
        "create_whoop_activity",
        {"activity_type": "sauna", "duration_minutes": 20},
        mock.ANY,
    )
    assert mock_client.messages.create.call_count == 2


@pytest.mark.asyncio
async def test_tool_use_loop_respects_max_iterations():
    """Tool loop stops after MAX_TOOL_ITERATIONS."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = "call_1"
    tool_block.name = "test"
    tool_block.input = {}

    tool_response = MagicMock()
    tool_response.content = [tool_block]
    tool_response.stop_reason = "tool_use"

    with patch("server.services.claude_service.anthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=tool_response)

        mock_executor = AsyncMock(return_value={"ok": True})

        from server.services.claude_service import _call_claude_with_tools
        result = await _call_claude_with_tools(
            "test", "test",
            [{"name": "test", "description": "t", "input_schema": {}}],
            mock_executor, MagicMock(),
        )

    assert "trouble" in result
    assert mock_client.messages.create.call_count == 3  # MAX_TOOL_ITERATIONS
