from dataclasses import dataclass
from datetime import datetime


@dataclass
class Meeting:
    id: str
    lead_id: str
    car_id: str
    google_event_id: str | None
    google_meet_link: str | None
    scheduled_at: datetime
    duration_minutes: int
    location: str
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
