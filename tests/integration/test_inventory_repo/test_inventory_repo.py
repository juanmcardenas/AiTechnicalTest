import pytest
from app.infrastructure.repositories.inventory_repo import InventoryRepository


async def test_get_cars_returns_available_cars(db_session):
    repo = InventoryRepository(db_session)
    cars = await repo.get_cars()
    assert len(cars) >= 10
    assert all(c.available for c in cars)


async def test_get_cars_filter_by_brand(db_session):
    repo = InventoryRepository(db_session)
    cars = await repo.get_cars({"brand": "Toyota"})
    assert len(cars) > 0
    assert all("toyota" in c.brand.lower() for c in cars)


async def test_get_cars_filter_by_condition(db_session):
    repo = InventoryRepository(db_session)
    cars = await repo.get_cars({"condition": "new"})
    assert all(c.condition == "new" for c in cars)


async def test_get_car_by_id_returns_none_for_unknown(db_session):
    repo = InventoryRepository(db_session)
    car = await repo.get_car_by_id("00000000-0000-0000-0000-000000000000")
    assert car is None


async def test_get_cars_filter_by_max_price(db_session):
    repo = InventoryRepository(db_session)
    cars = await repo.get_cars({"max_price": 25000})
    assert len(cars) > 0
    assert all(c.price <= 25000 for c in cars)
