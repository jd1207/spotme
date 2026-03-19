import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from unittest import mock


async def _mock_wait_for(coro, timeout):
    """await the coroutine like real wait_for does."""
    return await coro


@pytest.mark.asyncio
async def test_call_claude_returns_json_response():
    """_call_claude uses CLI subprocess and returns parsed JSON."""
    from server.services.claude_service import _call_claude

    proc = AsyncMock()
    proc.communicate.return_value = (b'{"response": "test reply", "layout": null}', b"")
    proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=proc):
        with patch("asyncio.wait_for", side_effect=_mock_wait_for):
            result = await _call_claude("test system prompt", "hello")

    assert '"response"' in result
    assert "test reply" in result


@pytest.mark.asyncio
async def test_call_claude_extracts_json_from_fenced_response():
    """_call_claude applies _extract_json to strip markdown fences."""
    from server.services.claude_service import _call_claude

    proc = AsyncMock()
    proc.communicate.return_value = (b'```json\n{"response": "fenced", "layout": null}\n```', b"")
    proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=proc):
        with patch("asyncio.wait_for", side_effect=_mock_wait_for):
            result = await _call_claude("sys", "msg")

    assert '"response"' in result
    assert "```" not in result


@pytest.mark.asyncio
async def test_call_claude_raises_on_cli_error():
    """_call_claude raises RuntimeError on non-zero exit code."""
    from server.services.claude_service import _call_claude

    proc = AsyncMock()
    proc.communicate.return_value = (b"", b"auth failed")
    proc.returncode = 1

    with patch("asyncio.create_subprocess_exec", return_value=proc):
        with patch("asyncio.wait_for", side_effect=_mock_wait_for):
            with pytest.raises(RuntimeError, match="claude cli failed"):
                await _call_claude("sys", "msg")


@pytest.mark.asyncio
async def test_tool_use_loop_executes_tool():
    """When Claude returns tool_calls, server executes and sends results back."""
    from server.services.claude_service import _call_claude_with_tools

    first_response = '{"response": "logging sauna", "tool_calls": [{"name": "create_whoop_activity", "arguments": {"activity_type": "sauna", "duration_minutes": 20}}]}'
    second_response = '{"response": "Logged 20-min sauna to Whoop.", "layout": null}'

    with patch("server.services.claude_service._call_claude", new_callable=AsyncMock) as mock_call:
        mock_call.side_effect = [first_response, second_response]
        mock_tool_executor = AsyncMock(return_value={"success": True, "activity_id": "uuid-123"})

        result = await _call_claude_with_tools(
            system_prompt="test",
            message="log a sauna",
            tools=[{
                "name": "create_whoop_activity",
                "description": "Log an activity",
                "input_schema": {
                    "type": "object",
                    "properties": {"activity_type": {"type": "string"}, "duration_minutes": {"type": "integer"}},
                    "required": ["activity_type", "duration_minutes"],
                },
            }],
            tool_executor=mock_tool_executor,
            db=MagicMock(),
        )

    assert "Logged 20-min sauna" in result
    mock_tool_executor.assert_called_once_with(
        "create_whoop_activity",
        {"activity_type": "sauna", "duration_minutes": 20},
        mock.ANY,
    )
    assert mock_call.call_count == 2
