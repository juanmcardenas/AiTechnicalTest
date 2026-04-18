from abc import ABC, abstractmethod
from app.domain.entities.car import Car


class IEmailService(ABC):
    @abstractmethod
    async def send_car_specs(self, recipient_email: str, car: Car) -> bool: ...
