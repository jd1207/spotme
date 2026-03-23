import pytest
from unittest.mock import AsyncMock, patch


async def _mock_wait_for(coro, timeout):
    """await the coroutine like real wait_for does."""
    return await coro


@pytest.mark.asyncio
async def test_call_claude_stateless_returns_json_response():
    """_call_claude_stateless uses CLI subprocess and returns parsed JSON."""
    from server.services.claude_service import _call_claude_stateless

    proc = AsyncMock()
    proc.communicate.return_value = (b'{"response": "test reply", "layout": null}', b"")
    proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=proc):
        with patch("asyncio.wait_for", side_effect=_mock_wait_for):
            result = await _call_claude_stateless("test system prompt", "hello")

    assert '"response"' in result
    assert "test reply" in result


@pytest.mark.asyncio
async def test_call_claude_stateless_extracts_json_from_fenced_response():
    """_call_claude_stateless applies _extract_json to strip markdown fences."""
    from server.services.claude_service import _call_claude_stateless

    proc = AsyncMock()
    proc.communicate.return_value = (b'```json\n{"response": "fenced", "layout": null}\n```', b"")
    proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=proc):
        with patch("asyncio.wait_for", side_effect=_mock_wait_for):
            result = await _call_claude_stateless("sys", "msg")

    assert '"response"' in result
    assert "```" not in result


@pytest.mark.asyncio
async def test_call_claude_stateless_raises_on_cli_error():
    """_call_claude_stateless raises RuntimeError on non-zero exit code."""
    from server.services.claude_service import _call_claude_stateless

    proc = AsyncMock()
    proc.communicate.return_value = (b"", b"auth failed")
    proc.returncode = 1

    with patch("asyncio.create_subprocess_exec", return_value=proc):
        with patch("asyncio.wait_for", side_effect=_mock_wait_for):
            with pytest.raises(RuntimeError, match="claude cli failed"):
                await _call_claude_stateless("sys", "msg")
