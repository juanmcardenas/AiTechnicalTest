from dataclasses import dataclass
from datetime import datetime, timedelta

SESSION_IDLE_MINUTES = 5


@dataclass
class Session:
    id: str
    lead_id: str
    started_at: datetime
    last_message_at: datetime
    created_at: datetime

    def is_active(self, now: datetime) -> bool:
        return now - self.last_message_at <= timedelta(minutes=SESSION_IDLE_MINUTES)
