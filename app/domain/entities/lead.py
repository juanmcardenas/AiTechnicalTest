from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class LeadStatus(str, Enum):
    NEW = "new"
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    CONVERTED = "converted"


@dataclass
class Lead:
    id: str
    telegram_chat_id: str
    name: str | None
    phone: str | None
    email: str | None
    status: LeadStatus
    preferred_language: str
    last_contacted_at: datetime | None
    created_at: datetime
    updated_at: datetime
