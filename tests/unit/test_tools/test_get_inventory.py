import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock
from app.domain.entities.car import Car
from app.application.services.tools.get_inventory import make_get_inventory_tool


@pytest.fixture
def sample_car():
    return Car(
        id="car-1", brand="Toyota", model="Corolla", year=2022,
        color="White", price=22500.0, km=28000, fuel_type="gasoline",
        transmission="automatic", condition="used", vin=None,
        description=None, image_url=None, available=True,
        created_at=datetime(2024, 1, 1),
    )


@pytest.fixture
def mock_repo(sample_car):
    repo = AsyncMock()
    repo.get_cars.return_value = [sample_car]
    return repo


async def test_get_inventory_no_filters(mock_repo, sample_car):
    tool = make_get_inventory_tool(mock_repo)
    result = await tool.ainvoke({})
    cars = json.loads(result)
    assert len(cars) == 1
    assert cars[0]["brand"] == "Toyota"


async def test_get_inventory_with_brand_filter(mock_repo):
    tool = make_get_inventory_tool(mock_repo)
    await tool.ainvoke({"brand": "Toyota"})
    call_args = mock_repo.get_cars.call_args[0][0]
    assert call_args.get("brand") == "Toyota"


async def test_get_inventory_returns_max_10(mock_repo, sample_car):
    mock_repo.get_cars.return_value = [sample_car] * 15
    tool = make_get_inventory_tool(mock_repo)
    result = await tool.ainvoke({})
    assert len(json.loads(result)) == 10
