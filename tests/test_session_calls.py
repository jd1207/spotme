import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from server.services.claude_service import (
    _call_claude_session,
    _call_claude_stateless,
    _session_lock,
)


@pytest.fixture
def mock_subprocess():
    proc = AsyncMock()
    proc.returncode = 0
    proc.communicate = AsyncMock(return_value=(
        json.dumps({"response": "test reply"}).encode(),
        b"",
    ))
    proc.kill = MagicMock()
    proc.wait = AsyncMock()
    return proc


async def _mock_wait_for(coro, timeout):
    """await the coroutine like real wait_for does."""
    return await coro


@pytest.mark.asyncio
async def test_session_call_uses_resume(mock_subprocess):
    with patch("asyncio.create_subprocess_exec", return_value=mock_subprocess) as mock_exec:
        with patch("asyncio.wait_for", side_effect=_mock_wait_for):
            result = await _call_claude_session(
                session_id="abc-123",
                message="hello",
                is_first=False,
            )
            args = mock_exec.call_args[0]
            assert "--resume" in args
            assert "abc-123" in args
            assert "--session-id" not in args


@pytest.mark.asyncio
async def test_session_call_uses_session_id_for_first(mock_subprocess):
    with patch("asyncio.create_subprocess_exec", return_value=mock_subprocess) as mock_exec:
        with patch("asyncio.wait_for", side_effect=_mock_wait_for):
            result = await _call_claude_session(
                session_id="abc-123",
                message="hello",
                is_first=True,
                system_prompt="you are a coach",
            )
            args = mock_exec.call_args[0]
            assert "--session-id" in args
            assert "abc-123" in args
            assert "--append-system-prompt" in args


@pytest.mark.asyncio
async def test_stateless_call_uses_no_session_persistence(mock_subprocess):
    with patch("asyncio.create_subprocess_exec", return_value=mock_subprocess) as mock_exec:
        with patch("asyncio.wait_for", side_effect=_mock_wait_for):
            result = await _call_claude_stateless("system", "message")
            args = mock_exec.call_args[0]
            assert "--no-session-persistence" in args
            assert "--resume" not in args


@pytest.mark.asyncio
async def test_session_lock_prevents_concurrent_calls(mock_subprocess):
    call_order = []

    async def slow_communicate():
        call_order.append("start")
        await asyncio.sleep(0.1)
        call_order.append("end")
        return (json.dumps({"response": "ok"}).encode(), b"")

    mock_subprocess.communicate = slow_communicate

    with patch("asyncio.create_subprocess_exec", return_value=mock_subprocess):
        with patch("asyncio.wait_for", side_effect=_mock_wait_for):
            await asyncio.gather(
                _call_claude_session("id", "msg1", is_first=False),
                _call_claude_session("id", "msg2", is_first=False),
            )
    assert call_order == ["start", "end", "start", "end"]
