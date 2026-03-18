import pytest
from datetime import datetime
from zoneinfo import ZoneInfo


def test_today_eastern_returns_eastern_date():
    from server.config import today_eastern, TIMEZONE
    result = today_eastern()
    expected = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    assert result == expected


def test_today_eastern_format():
    from server.config import today_eastern
    result = today_eastern()
    assert len(result) == 10
    assert result[4] == "-"
    assert result[7] == "-"


def test_recovery_zone_green():
    from server.utils import recovery_zone
    assert recovery_zone(85.0) == "GREEN"
    assert recovery_zone(67.0) == "GREEN"


def test_recovery_zone_yellow():
    from server.utils import recovery_zone
    assert recovery_zone(66.0) == "YELLOW"
    assert recovery_zone(34.0) == "YELLOW"


def test_recovery_zone_red():
    from server.utils import recovery_zone
    assert recovery_zone(33.0) == "RED"
    assert recovery_zone(0.0) == "RED"


def test_recovery_zone_none():
    from server.utils import recovery_zone
    assert recovery_zone(None) == "UNKNOWN"
