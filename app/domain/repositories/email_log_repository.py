from abc import ABC, abstractmethod


class IEmailLogRepository(ABC):
    @abstractmethod
    async def log(
        self,
        lead_id: str,
        car_id: str,
        recipient: str,
        subject: str,
        template: str,
        success: bool,
        error: str | None,
    ) -> None: ...
