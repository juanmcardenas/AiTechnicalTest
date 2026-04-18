from abc import ABC, abstractmethod
from app.domain.entities.lead import Lead


class ILeadRepository(ABC):
    @abstractmethod
    async def get_or_create(self, telegram_chat_id: str) -> Lead: ...

    @abstractmethod
    async def update(self, lead: Lead) -> Lead: ...
