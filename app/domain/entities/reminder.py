from dataclasses import dataclass
from datetime import datetime


@dataclass
class Reminder:
    id: str
    lead_id: str
    remind_at: datetime
    message: str
    sent: bool
    sent_at: datetime | None
    created_at: datetime
