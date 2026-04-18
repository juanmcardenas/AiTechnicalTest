from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import settings


def default_tz() -> ZoneInfo:
    return ZoneInfo(settings.default_timezone)


def parse_local_datetime(s: str) -> datetime:
    """Parse an ISO8601 datetime string. If naive, attach the default timezone."""
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=default_tz())
    return dt


def format_for_user(dt: datetime) -> str:
    """Format a timezone-aware datetime in the default timezone, including tz abbreviation."""
    local = dt.astimezone(default_tz())
    return local.strftime("%A, %B %-d, %Y at %-I:%M %p %Z")
