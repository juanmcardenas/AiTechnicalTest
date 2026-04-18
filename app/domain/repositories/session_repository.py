from abc import ABC, abstractmethod
from datetime import datetime
from app.domain.entities.session import Session


class ISessionRepository(ABC):
    @abstractmethod
    async def get_active_for_lead(self, lead_id: str, now: datetime) -> Session | None: ...

    @abstractmethod
    async def create(self, lead_id: str) -> Session: ...

    @abstractmethod
    async def touch(self, session_id: str, ts: datetime) -> None: ...
