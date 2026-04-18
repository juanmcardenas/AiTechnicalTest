from sqlalchemy import select
from app.domain.entities.car import Car
from app.domain.repositories.inventory_repository import IInventoryRepository
from app.infrastructure.database.models.inventory_model import InventoryORM
from app.infrastructure.repositories.base_repository import BaseRepository


class InventoryRepository(BaseRepository, IInventoryRepository):
    async def get_cars(self, filters: dict | None = None) -> list[Car]:
        stmt = select(InventoryORM).where(InventoryORM.available == True)  # noqa: E712
        if filters:
            if filters.get("brand"):
                stmt = stmt.where(InventoryORM.brand.ilike(f"%{filters['brand']}%"))
            if filters.get("model"):
                stmt = stmt.where(InventoryORM.model.ilike(f"%{filters['model']}%"))
            if filters.get("year"):
                stmt = stmt.where(InventoryORM.year == filters["year"])
            if filters.get("color"):
                stmt = stmt.where(InventoryORM.color.ilike(f"%{filters['color']}%"))
            if filters.get("min_price"):
                stmt = stmt.where(InventoryORM.price >= filters["min_price"])
            if filters.get("max_price"):
                stmt = stmt.where(InventoryORM.price <= filters["max_price"])
            if filters.get("min_km"):
                stmt = stmt.where(InventoryORM.km >= filters["min_km"])
            if filters.get("max_km"):
                stmt = stmt.where(InventoryORM.km <= filters["max_km"])
            if filters.get("condition"):
                stmt = stmt.where(InventoryORM.condition == filters["condition"])
            if filters.get("fuel_type"):
                stmt = stmt.where(InventoryORM.fuel_type == filters["fuel_type"])
            if filters.get("transmission"):
                stmt = stmt.where(InventoryORM.transmission == filters["transmission"])
        rows = (await self.session.execute(stmt)).scalars().all()
        return [self._to_domain(r) for r in rows]

    async def get_car_by_id(self, car_id: str) -> Car | None:
        stmt = select(InventoryORM).where(InventoryORM.id == car_id)
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        return self._to_domain(row) if row else None

    def _to_domain(self, r: InventoryORM) -> Car:
        return Car(
            id=str(r.id), brand=r.brand, model=r.model, year=r.year,
            color=r.color, price=float(r.price), km=r.km,
            fuel_type=r.fuel_type, transmission=r.transmission,
            condition=r.condition, vin=r.vin, description=r.description,
            image_url=r.image_url, available=r.available, created_at=r.created_at,
        )
