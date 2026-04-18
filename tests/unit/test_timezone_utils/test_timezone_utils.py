from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.application.services.timezone_utils import (
    default_tz,
    format_for_user,
    parse_local_datetime,
)


def test_default_tz_is_america_new_york():
    tz = default_tz()
    assert isinstance(tz, ZoneInfo)
    assert str(tz) == "America/New_York"


def test_parse_local_datetime_attaches_default_tz_to_naive():
    dt = parse_local_datetime("2026-07-15T14:00:00")
    assert dt.tzinfo is not None
    assert dt.utcoffset() == datetime(2026, 7, 15, 14, 0, tzinfo=ZoneInfo("America/New_York")).utcoffset()


def test_parse_local_datetime_preserves_explicit_offset():
    dt = parse_local_datetime("2026-07-15T14:00:00+00:00")
    assert dt.utcoffset().total_seconds() == 0


def test_format_for_user_renders_eastern_with_tz_name():
    utc_instant = datetime(2026, 7, 15, 18, 0, tzinfo=timezone.utc)
    text = format_for_user(utc_instant)
    assert "2026" in text
    assert "EDT" in text or "EST" in text


def test_format_for_user_winter_shows_est():
    utc_instant = datetime(2026, 1, 15, 18, 0, tzinfo=timezone.utc)
    text = format_for_user(utc_instant)
    assert "EST" in text
