from abc import ABC, abstractmethod
from app.domain.entities.car import Car


class IInventoryRepository(ABC):
    @abstractmethod
    async def get_cars(self, filters: dict | None = None) -> list[Car]: ...

    @abstractmethod
    async def get_car_by_id(self, car_id: str) -> Car | None: ...
