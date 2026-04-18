from datetime import datetime, timedelta, timezone

from app.domain.entities.session import SESSION_IDLE_MINUTES, Session


def test_session_is_active_true_within_window():
    now = datetime(2026, 4, 18, 12, 0, tzinfo=timezone.utc)
    last = now - timedelta(minutes=SESSION_IDLE_MINUTES - 1)
    s = Session(
        id="s1", lead_id="l1",
        started_at=last, last_message_at=last, created_at=last,
    )
    assert s.is_active(now) is True


def test_session_is_active_true_at_boundary():
    now = datetime(2026, 4, 18, 12, 0, tzinfo=timezone.utc)
    last = now - timedelta(minutes=SESSION_IDLE_MINUTES)
    s = Session(
        id="s1", lead_id="l1",
        started_at=last, last_message_at=last, created_at=last,
    )
    assert s.is_active(now) is True


def test_session_is_active_false_past_boundary():
    now = datetime(2026, 4, 18, 12, 0, tzinfo=timezone.utc)
    last = now - timedelta(minutes=SESSION_IDLE_MINUTES + 1)
    s = Session(
        id="s1", lead_id="l1",
        started_at=last, last_message_at=last, created_at=last,
    )
    assert s.is_active(now) is False


def test_session_idle_minutes_is_five():
    assert SESSION_IDLE_MINUTES == 5
