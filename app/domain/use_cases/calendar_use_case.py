from abc import ABC, abstractmethod
from datetime import datetime


class ICalendarService(ABC):
    @abstractmethod
    async def get_available_slots(self, days_ahead: int = 14) -> list[dict]: ...

    @abstractmethod
    async def create_event(
        self,
        title: str,
        start: datetime,
        end: datetime,
        attendee_email: str | None,
        description: str,
    ) -> str: ...
