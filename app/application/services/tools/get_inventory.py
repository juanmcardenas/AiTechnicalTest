import json
from dataclasses import asdict
from typing import Literal
from langchain_core.tools import tool
from app.domain.repositories.inventory_repository import IInventoryRepository


def make_get_inventory_tool(repo: IInventoryRepository):
    @tool
    async def get_inventory(
        brand: str | None = None,
        model: str | None = None,
        year: int | None = None,
        color: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        min_km: int | None = None,
        max_km: int | None = None,
        condition: Literal["new", "used", "certified"] | None = None,
        fuel_type: Literal["gasoline", "diesel", "electric", "hybrid"] | None = None,
        transmission: Literal["automatic", "manual"] | None = None,
    ) -> str:
        """Search available car inventory. All filters optional. Returns JSON array (max 10).
        Use when the customer asks about vehicles, models, prices, colors, km, or specs."""
        filters = {
            "brand": brand, "model": model, "year": year, "color": color,
            "min_price": min_price, "max_price": max_price,
            "min_km": min_km, "max_km": max_km,
            "condition": condition, "fuel_type": fuel_type, "transmission": transmission,
        }
        filters = {k: v for k, v in filters.items() if v is not None}
        cars = await repo.get_cars(filters if filters else None)
        return json.dumps([asdict(c) for c in cars[:10]], default=str)

    return get_inventory
