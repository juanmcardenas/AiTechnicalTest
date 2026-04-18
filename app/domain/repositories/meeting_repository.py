from abc import ABC, abstractmethod
from app.domain.entities.meeting import Meeting


class IMeetingRepository(ABC):
    @abstractmethod
    async def create(self, meeting: Meeting) -> Meeting: ...

    @abstractmethod
    async def get_by_lead(self, lead_id: str) -> list[Meeting]: ...
