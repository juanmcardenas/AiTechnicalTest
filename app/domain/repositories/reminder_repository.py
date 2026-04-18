from abc import ABC, abstractmethod
from datetime import datetime
from app.domain.entities.reminder import Reminder


class IReminderRepository(ABC):
    @abstractmethod
    async def create(self, reminder: Reminder) -> Reminder: ...

    @abstractmethod
    async def get_pending(self, before: datetime) -> list[Reminder]: ...

    @abstractmethod
    async def mark_sent(self, reminder_id: str) -> None: ...
